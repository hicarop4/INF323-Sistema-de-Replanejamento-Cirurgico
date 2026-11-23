from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Intervalo:
    """Período de tempo fechado no início e aberto no fim: [inicio, fim)."""

    inicio: datetime
    fim: datetime

    def __post_init__(self):
        if self.fim <= self.inicio:
            raise ValueError("O fim do intervalo deve ser depois do início")

    @classmethod
    def a_partir(cls, inicio: datetime, minutos: int) -> "Intervalo":
        return cls(inicio, inicio + timedelta(minutes=minutos))

    @property
    def duracao_min(self) -> int:
        return int((self.fim - self.inicio).total_seconds() // 60)

    def sobrepoe(self, outro: "Intervalo") -> bool:
        return self.inicio < outro.fim and outro.inicio < self.fim

    def contem(self, outro: "Intervalo") -> bool:
        return self.inicio <= outro.inicio and outro.fim <= self.fim

    def deslocado(self, minutos: int) -> "Intervalo":
        delta = timedelta(minutes=minutos)
        return Intervalo(self.inicio + delta, self.fim + delta)

    def estendido(self, minutos: int) -> "Intervalo":
        return Intervalo(self.inicio, self.fim + timedelta(minutes=minutos))

    def minutos_ate(self, momento: datetime) -> int:
        return int((momento - self.fim).total_seconds() // 60)
