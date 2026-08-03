"""SWIM: periodic randomized ping/ping-req probing with piggybacked
gossip dissemination and a suspicion state to reduce false positives.

Everything below runs on a single asyncio event loop, so state mutation
never needs a lock: as long as a method doesn't ``await`` in the middle
of a read-modify-write, it's already atomic with respect to every other
coroutine on this loop.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

from dssd.addr import format_addr, split_addr

from .message import Message, MsgType, Sender
from .state import Event, EventType, Member, State, supersedes

MAX_TRANSMITS_PER_UPDATE = 5  # gossip retransmit budget per state change
MAX_UPDATES_PER_MESSAGE = 8


@dataclass
class Config:
    id: str
    bind_host: str = "127.0.0.1"
    bind_port: int = 0

    protocol_period: float = 0.2  # how often to probe a random member
    ping_timeout: float = 0.05  # time to wait for a direct or indirect ack
    indirect_ping_count: int = 3  # helpers used for indirect probing
    suspicion_timeout: float = 0.0  # 0 means "derive from protocol_period"

    def __post_init__(self) -> None:
        if self.suspicion_timeout <= 0:
            self.suspicion_timeout = 5 * self.protocol_period


@dataclass
class _BroadcastItem:
    update: Member
    transmits: int = 0


class Node:
    """A SWIM agent. Call start() to begin probing; stop() to shut down."""

    def __init__(self, config: Config) -> None:
        self.cfg = config
        self.events: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)

        self._members: dict[str, Member] = {}
        self._incarnation = 0

        self._transport: asyncio.DatagramTransport | None = None
        self._bind_addr: str | None = None

        self._waiters: dict[int, asyncio.Future] = {}
        self._seq_no = 0
        self._broadcasts: list[_BroadcastItem] = []

        self._probe_task: asyncio.Task | None = None
        self._background: set[asyncio.Task] = set()
        self._stopped = False

    @property
    def id(self) -> str:
        return self.cfg.id

    @property
    def addr(self) -> str:
        if self._bind_addr is None:
            raise RuntimeError("swim: node not started")
        return self._bind_addr

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _Protocol(self),
            local_addr=(self.cfg.bind_host, self.cfg.bind_port),
        )
        self._transport = transport
        host, port = transport.get_extra_info("sockname")[:2]
        self._bind_addr = format_addr(host, port)
        self._probe_task = asyncio.create_task(self._probe_loop())

    async def stop(self) -> None:
        """Shuts the node down. Safe to call more than once."""
        if self._stopped:
            return
        self._stopped = True
        if self._probe_task is not None:
            self._probe_task.cancel()
        if self._transport is not None:
            self._transport.close()
        pending = [self._probe_task, *self._background]
        await asyncio.gather(*(t for t in pending if t is not None), return_exceptions=True)

    def members(self) -> list[Member]:
        """A snapshot of everything this node currently knows, including itself."""
        out = [Member(self.cfg.id, self.addr, State.ALIVE, self._incarnation)]
        out.extend(self._members.values())
        return out

    def learn(self, id: str, addr: str) -> None:
        """Injects knowledge of a member directly, without a UDP round
        trip. Used by the gRPC-facing Join RPC; ordinary gossip takes
        over from there."""
        self._merge_update(Member(id=id, addr=addr, state=State.ALIVE, incarnation=0))

    async def join(self, contact_addr: str) -> None:
        """Bootstraps this node's membership view from an existing member."""
        seq = self._next_seq()
        fut = self._register_waiter(seq)
        try:
            self._send(contact_addr, Message(type=MsgType.JOIN, seq=seq, sender=self._self_sender()))
            try:
                await asyncio.wait_for(asyncio.shield(fut), timeout=3 * self.cfg.ping_timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"swim: join {contact_addr} timed out") from None
        finally:
            self._unregister_waiter(seq)

    def leave(self) -> None:
        """Announces this node's departure to a handful of peers so they
        don't have to wait out the full suspicion timeout to learn it's
        gone."""
        self_dead = Member(self.cfg.id, self.addr, State.DEAD, self._incarnation)
        for peer in self._pick_random_members(self.cfg.indirect_ping_count + 2, exclude=""):
            self._send(peer.addr, Message(type=MsgType.GOSSIP, seq=self._next_seq(), updates=(self_dead,)))

    # --- internals ---

    def _self_sender(self) -> Sender:
        return Sender(id=self.cfg.id, addr=self.addr, incarnation=self._incarnation)

    def _next_seq(self) -> int:
        self._seq_no += 1
        return self._seq_no

    def _send(self, addr: str, msg: Message) -> None:
        host, port = split_addr(addr)
        assert self._transport is not None
        self._transport.sendto(msg.encode(), (host, port))

    def _emit(self, event: Event) -> None:
        try:
            self.events.put_nowait(event)
        except asyncio.QueueFull:
            pass  # slow consumer; drop rather than block the protocol loop

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    def _register_waiter(self, seq: int) -> asyncio.Future:
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._waiters[seq] = fut
        return fut

    def _unregister_waiter(self, seq: int) -> None:
        self._waiters.pop(seq, None)

    def _resolve_waiter(self, seq: int) -> None:
        fut = self._waiters.pop(seq, None)
        if fut is not None and not fut.done():
            fut.set_result(None)

    # --- probing ---

    async def _probe_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.cfg.protocol_period)
                await self._probe_once()
        except asyncio.CancelledError:
            pass

    async def _probe_once(self) -> None:
        target = self._pick_probe_target()
        if target is None:
            return

        seq = self._next_seq()
        fut = self._register_waiter(seq)
        try:
            self._send(
                target.addr,
                Message(type=MsgType.PING, seq=seq, sender=self._self_sender(), updates=tuple(self._take_broadcasts())),
            )
            if await self._wait_ack(fut, self.cfg.ping_timeout):
                return

            for helper in self._pick_random_members(self.cfg.indirect_ping_count, exclude=target.id):
                self._send(
                    helper.addr,
                    Message(type=MsgType.PING_REQ, seq=seq, sender=self._self_sender(), target_addr=target.addr),
                )
            if await self._wait_ack(fut, self.cfg.ping_timeout):
                return

            self._mark_suspect(target)
        finally:
            self._unregister_waiter(seq)

    @staticmethod
    async def _wait_ack(fut: asyncio.Future, timeout: float) -> bool:
        try:
            await asyncio.wait_for(asyncio.shield(fut), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def _relay_ping(self, req: Message) -> None:
        """Pings req.target_addr on behalf of a ping-req sender and
        forwards an ack back if the target responds."""
        seq = self._next_seq()
        fut = self._register_waiter(seq)
        try:
            self._send(req.target_addr, Message(type=MsgType.PING, seq=seq, sender=self._self_sender()))
            if await self._wait_ack(fut, self.cfg.ping_timeout):
                self._send(req.sender.addr, Message(type=MsgType.ACK, seq=req.seq, sender=self._self_sender()))
        finally:
            self._unregister_waiter(seq)

    def _mark_suspect(self, target: Member) -> None:
        current = self._members.get(target.id)
        if current is None or current.state != State.ALIVE:
            return
        updated = Member(current.id, current.addr, State.SUSPECT, current.incarnation)
        self._members[target.id] = updated
        self._enqueue_broadcast(updated)
        self._spawn(self._suspicion_timer(target.id, current.incarnation))

    async def _suspicion_timer(self, id: str, incarnation: int) -> None:
        try:
            await asyncio.sleep(self.cfg.suspicion_timeout)
        except asyncio.CancelledError:
            return
        self._handle_suspicion_timeout(id, incarnation)

    def _handle_suspicion_timeout(self, id: str, incarnation: int) -> None:
        current = self._members.get(id)
        if current is None or current.state != State.SUSPECT or current.incarnation != incarnation:
            return
        updated = Member(current.id, current.addr, State.DEAD, current.incarnation)
        self._members[id] = updated
        self._enqueue_broadcast(updated)
        self._emit(Event(EventType.FAILED, updated))

    def _pick_probe_target(self) -> Member | None:
        candidates = [m for m in self._members.values() if m.state != State.DEAD]
        return random.choice(candidates) if candidates else None

    def _pick_random_members(self, k: int, exclude: str) -> list[Member]:
        candidates = [m for id, m in self._members.items() if id != exclude and m.state != State.DEAD]
        random.shuffle(candidates)
        return candidates[:k]

    # --- receiving ---

    def _handle_message(self, msg: Message) -> None:
        if msg.sender.id and msg.sender.id != self.cfg.id:
            self._merge_update(Member(msg.sender.id, msg.sender.addr, State.ALIVE, msg.sender.incarnation))
        for update in msg.updates:
            self._merge_update(update)

        if msg.type == MsgType.PING:
            self._reply(msg, MsgType.ACK, tuple(self._take_broadcasts()))
        elif msg.type == MsgType.JOIN:
            self._reply(msg, MsgType.JOIN_ACK, tuple(self._members.values()))
        elif msg.type == MsgType.PING_REQ:
            self._spawn(self._relay_ping(msg))
        elif msg.type in (MsgType.ACK, MsgType.JOIN_ACK):
            self._resolve_waiter(msg.seq)
        # GOSSIP carries no reply; its updates were already merged above.

    def _reply(self, req: Message, msg_type: MsgType, updates: tuple[Member, ...]) -> None:
        self._send(req.sender.addr, Message(type=msg_type, seq=req.seq, sender=self._self_sender(), updates=updates))

    def _merge_update(self, update: Member) -> bool:
        """Applies a gossiped state update, reconciling it against what's
        currently known per SWIM's incarnation/state precedence rule.
        Returns whether the update changed local state."""
        if update.id == self.cfg.id:
            return self._merge_self(update)

        current = self._members.get(update.id)
        if current is None:
            if update.state == State.DEAD:
                return False
            self._members[update.id] = update
            self._enqueue_broadcast(update)
            self._emit(Event(EventType.JOINED, update))
            return True

        if not supersedes(update, current):
            return False

        old_state = current.state
        self._members[update.id] = update
        self._enqueue_broadcast(update)

        event_type = _event_for_transition(old_state, update.state)
        if event_type is not None:
            self._emit(Event(event_type, update))

        if update.state == State.SUSPECT and old_state != State.SUSPECT:
            self._spawn(self._suspicion_timer(update.id, update.incarnation))

        return True

    def _merge_self(self, update: Member) -> bool:
        """A gossiped update about this node itself: any non-Alive claim
        at or above our current incarnation is a suspicion or death
        rumor that must be refuted by bumping our incarnation and
        rebroadcasting Alive."""
        if update.state == State.ALIVE or update.incarnation < self._incarnation:
            return False
        self._incarnation = update.incarnation + 1
        self._enqueue_broadcast(Member(self.cfg.id, self.addr, State.ALIVE, self._incarnation))
        return True

    # --- gossip dissemination ---

    def _enqueue_broadcast(self, update: Member) -> None:
        for i, item in enumerate(self._broadcasts):
            if item.update.id == update.id:
                self._broadcasts[i] = _BroadcastItem(update)
                return
        self._broadcasts.append(_BroadcastItem(update))

    def _take_broadcasts(self) -> list[Member]:
        """Returns the updates due for retransmission, preferring the
        least-transmitted ones, and drops any that have exhausted their
        retransmit budget."""
        self._broadcasts.sort(key=lambda item: item.transmits)

        out: list[Member] = []
        kept: list[_BroadcastItem] = []
        for item in self._broadcasts:
            if len(out) < MAX_UPDATES_PER_MESSAGE:
                out.append(item.update)
                item.transmits += 1
            if item.transmits < MAX_TRANSMITS_PER_UPDATE:
                kept.append(item)
        self._broadcasts = kept
        return out


def _event_for_transition(old: State, new: State) -> EventType | None:
    if new == State.DEAD and old != State.DEAD:
        return EventType.FAILED
    if new == State.ALIVE and old != State.ALIVE:
        return EventType.RECOVERED
    return None


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, node: Node) -> None:
        self._node = node

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            msg = Message.decode(data)
        except Exception:
            return
        self._node._handle_message(msg)
