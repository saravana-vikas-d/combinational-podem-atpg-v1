from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class GateType(Enum):
    AND = auto()
    OR = auto()
    NAND = auto()
    NOR = auto()
    NOT = auto()
    BUF = auto()
    XOR = auto()
    XNOR = auto()

    @classmethod
    def from_v(cls, keyword: str) -> GateType:
        """Map a Verilog primitive keyword to a GateType."""
        mapping = {
            "and": cls.AND,
            "or": cls.OR,
            "nand": cls.NAND,
            "nor": cls.NOR,
            "not": cls.NOT,
            "buf": cls.BUF,
            "xor": cls.XOR,
            "xnor": cls.XNOR,
        }
        key = keyword.lower()
        try:
            return mapping[key]
        except KeyError as exc:
            raise ValueError(f"unsupported gate type: {keyword!r}") from exc


from logic5 import Logic5


@dataclass
class Signal:
    """A primary port or internal wire — fault site and connectivity node."""

    name: str
    is_pi: bool = False
    is_po: bool = False
    driver: Gate | None = None
    fanouts: list[tuple[Gate, int]] = field(default_factory=list)
    level: int = -1
    value: Logic5 = Logic5.X


@dataclass
class Gate:
    """A primitive gate instance connecting input signals to one output."""

    id: int
    instance_name: str
    type: GateType
    inputs: list[Signal]
    output: Signal
    level: int = -1


@dataclass
class Circuit:
    """Parsed netlist: signals, gates, ordered ports, and levelized gate groups."""

    name: str
    signals: dict[str, Signal] = field(default_factory=dict)
    gates: list[Gate] = field(default_factory=list)
    primary_inputs: list[Signal] = field(default_factory=list)
    primary_outputs: list[Signal] = field(default_factory=list)
    levels: list[list[Gate]] = field(default_factory=list)
