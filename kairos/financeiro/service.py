"""Business rules (service layer) for the "financeiro" (student plan &
value) domain.

Receives raw form values (strings or None), normalizes and validates them
(architecture rule 6: empty means NULL, never a silent fake default), and
persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown to the coach (architecture rule 10); code and
identifiers stay in English.
"""

import datetime
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from sqlalchemy import and_, func, select

from kairos.db import session_scope
from kairos.financeiro.models import Despesa, Pagamento, PlanoAluno
from kairos.alunos.models import Aluno

logger = logging.getLogger(__name__)

FORMATOS_VALIDOS = ("digital", "grupo", "individual")

CATEGORIAS_DESPESA = (
    "aluguel",
    "equipamento",
    "software",
    "divulgacao",
    "formacao",
    "outros",
)


class ValidationError(Exception):
    """Raised when user-supplied data is invalid.

    The exception message is in Portuguese and ready for display.
    """


def _normalize(value: Optional[str]) -> Optional[str]:
    """Strip a raw string; empty or whitespace-only becomes None."""
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _parse_formato_required(value: Optional[str]) -> str:
    """Parse a required plan format, must be one of :data:`FORMATOS_VALIDOS`.

    Raises :class:`ValidationError` when missing or not a valid format.
    """
    value = _normalize(value)
    if value is None or value not in FORMATOS_VALIDOS:
        raise ValidationError("Formato inválido.")
    return value


def _parse_valor_required(value: Optional[str]) -> Decimal:
    """Parse a required monetary value, accepting comma or dot.

    Raises :class:`ValidationError` when missing, not a valid number, or not
    strictly positive.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Valor é obrigatório.")
    try:
        number = Decimal(value.replace(",", "."))
    except InvalidOperation:
        raise ValidationError("Valor inválido.")
    if number <= 0:
        raise ValidationError("Valor deve ser positivo.")
    return number


def _parse_ciclo_optional(value: Optional[str]) -> Optional[int]:
    """Parse an optional billing cycle (in months).

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when filled in
    but not a valid, strictly positive integer.
    """
    value = _normalize(value)
    if value is None:
        return None
    try:
        number = int(value)
    except ValueError:
        raise ValidationError("Ciclo inválido.")
    if number <= 0:
        raise ValidationError("Ciclo deve ser positivo.")
    return number


def _parse_inicio_optional(value: Optional[str]) -> Optional[datetime.date]:
    """Parse an optional ISO "YYYY-MM-DD" start date.

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when filled in
    but not a valid date.
    """
    value = _normalize(value)
    if value is None:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValidationError("Início inválido.")


def _to_dict(plano: PlanoAluno) -> Dict[str, Any]:
    """Extract a PlanoAluno's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": plano.id,
        "aluno_id": plano.aluno_id,
        "formato": plano.formato,
        "valor": plano.valor,
        "ciclo_meses": plano.ciclo_meses,
        "inicio": plano.inicio,
        "observacao": plano.observacao,
        "created_at": plano.created_at,
    }


def set_plano(
    aluno_id: int,
    *,
    formato: Optional[str] = None,
    valor: Optional[str] = None,
    ciclo_meses: Optional[str] = None,
    inicio: Optional[str] = None,
    observacao: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update (upsert) the single plan of a student.

    Raw form values are normalized and validated before anything touches the
    database; when invalid, :class:`ValidationError` (message in Portuguese)
    is raised and nothing is persisted.

    At most one PlanoAluno exists per student (aluno_id unique). When one
    already exists it is updated in place; otherwise a new one is created.

    The existence of ``aluno_id`` is not checked here — that is the caller
    route's responsibility (404 handling).
    """
    parsed_formato = _parse_formato_required(formato)
    parsed_valor = _parse_valor_required(valor)
    parsed_ciclo = _parse_ciclo_optional(ciclo_meses)
    parsed_inicio = _parse_inicio_optional(inicio)
    parsed_observacao = _normalize(observacao)

    with session_scope() as session:
        query = select(PlanoAluno).where(PlanoAluno.aluno_id == aluno_id)
        plano = session.execute(query).scalar_one_or_none()

        if plano is None:
            plano = PlanoAluno(aluno_id=aluno_id)
            session.add(plano)

        plano.formato = parsed_formato
        plano.valor = parsed_valor
        plano.ciclo_meses = parsed_ciclo
        plano.inicio = parsed_inicio
        plano.observacao = parsed_observacao

        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(plano)  # loads server-generated values (created_at)
        result = _to_dict(plano)

    logger.info("PlanoAluno set: aluno_id=%s", result["aluno_id"])
    return result


def get_plano(aluno_id: int) -> Optional[Dict[str, Any]]:
    """Return a student's plan as a plain dict, or None when there is
    none."""
    with session_scope() as session:
        query = select(PlanoAluno).where(PlanoAluno.aluno_id == aluno_id)
        plano = session.execute(query).scalar_one_or_none()
        if plano is None:
            return None
        return _to_dict(plano)


def remover_plano(aluno_id: int) -> bool:
    """Remove a student's plan.

    Returns True when a plan existed and was removed, False when there was
    none.
    """
    with session_scope() as session:
        query = select(PlanoAluno).where(PlanoAluno.aluno_id == aluno_id)
        plano = session.execute(query).scalar_one_or_none()
        if plano is None:
            return False
        session.delete(plano)
        logger.info("PlanoAluno removed: aluno_id=%s", aluno_id)
        return True


def resumo_financeiro() -> Dict[str, Any]:
    """Return financial indicators over active students with a plan.

    ``mrr`` is the sum of the plan value of every student whose status is
    "active" and who has a plan (Decimal, 0 when there are none).
    ``alunos_com_plano`` is how many such students there are.
    ``ticket_medio`` is ``mrr`` divided by ``alunos_com_plano``, rounded to 2
    decimal places, or None when there are no such students (never a fake
    zero — rule 6). Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(PlanoAluno.valor)
            .join(Aluno, PlanoAluno.aluno_id == Aluno.id)
            .where(Aluno.status == "active")
        )
        valores = session.execute(query).scalars().all()

    mrr = sum(valores, Decimal("0"))
    alunos_com_plano = len(valores)
    ticket_medio = (
        (mrr / alunos_com_plano).quantize(Decimal("0.01"))
        if alunos_com_plano > 0
        else None
    )

    return {
        "mrr": mrr,
        "ticket_medio": ticket_medio,
        "alunos_com_plano": alunos_com_plano,
    }


def _parse_data_pagamento(value: Optional[str]) -> datetime.date:
    """Parse a payment date, defaulting to today when empty.

    Empty or whitespace-only values become today's date (this is the one
    explicit default in this module: an unspecified payment date means "paid
    today", not "no data"). Raises :class:`ValidationError` when filled in
    but not a valid ISO "YYYY-MM-DD" date.
    """
    value = _normalize(value)
    if value is None:
        return datetime.date.today()
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValidationError("Data de pagamento inválida.")


def _to_pagamento_dict(p: Pagamento) -> Dict[str, Any]:
    """Extract a Pagamento's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": p.id,
        "aluno_id": p.aluno_id,
        "ano": p.ano,
        "mes": p.mes,
        "valor": p.valor,
        "data_pagamento": p.data_pagamento,
        "observacao": p.observacao,
        "created_at": p.created_at,
    }


def registrar_pagamento(
    aluno_id: int,
    *,
    ano: int,
    mes: int,
    valor: Optional[str] = None,
    data_pagamento: Optional[str] = None,
    observacao: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update (upsert) a student's payment for a given competence.

    Raw form values are normalized and validated before anything touches the
    database; when invalid, :class:`ValidationError` (message in Portuguese)
    is raised and nothing is persisted.

    At most one Pagamento exists per (aluno_id, ano, mes) — see the unique
    constraint. When one already exists it is updated in place; otherwise a
    new one is created.

    The existence of ``aluno_id`` is not checked here — that is the caller
    route's responsibility (404 handling).
    """
    parsed_valor = _parse_valor_required(valor)
    parsed_data_pagamento = _parse_data_pagamento(data_pagamento)
    parsed_observacao = _normalize(observacao)

    with session_scope() as session:
        query = select(Pagamento).where(
            Pagamento.aluno_id == aluno_id,
            Pagamento.ano == ano,
            Pagamento.mes == mes,
        )
        pagamento = session.execute(query).scalar_one_or_none()

        if pagamento is None:
            pagamento = Pagamento(aluno_id=aluno_id, ano=ano, mes=mes)
            session.add(pagamento)

        pagamento.valor = parsed_valor
        pagamento.data_pagamento = parsed_data_pagamento
        pagamento.observacao = parsed_observacao

        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(pagamento)  # loads server-generated values (created_at)
        result = _to_pagamento_dict(pagamento)

    logger.info(
        "Pagamento registrado: aluno_id=%s %s/%s",
        result["aluno_id"],
        result["mes"],
        result["ano"],
    )
    return result


def remover_pagamento(pagamento_id: int) -> bool:
    """Remove a payment.

    Returns True when a payment existed and was removed, False when there
    was none.
    """
    with session_scope() as session:
        pagamento = session.get(Pagamento, pagamento_id)
        if pagamento is None:
            return False
        session.delete(pagamento)
        logger.info("Pagamento removed: pagamento_id=%s", pagamento_id)
        return True


def get_pagamento(pagamento_id: int) -> Optional[Dict[str, Any]]:
    """Return a payment as a plain dict, or None when there is none."""
    with session_scope() as session:
        pagamento = session.get(Pagamento, pagamento_id)
        if pagamento is None:
            return None
        return _to_pagamento_dict(pagamento)


def pagamentos_do_aluno(aluno_id: int) -> list:
    """Return all payments of a student, most recent competence first.

    Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(Pagamento)
            .where(Pagamento.aluno_id == aluno_id)
            .order_by(Pagamento.ano.desc(), Pagamento.mes.desc())
        )
        pagamentos = session.execute(query).scalars().all()
        return [_to_pagamento_dict(p) for p in pagamentos]


def recebimentos_do_mes(ano: int, mes: int) -> list:
    """Return, for every active student with a plan, whether they have paid
    for the given competence (ano/mes).

    Each item is a dict with the student's plan value, whether it was paid,
    and (when paid) the payment's id, value and date. Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(
                Aluno.id,
                Aluno.name,
                PlanoAluno.valor,
                Pagamento.id,
                Pagamento.valor,
                Pagamento.data_pagamento,
            )
            .join(PlanoAluno, PlanoAluno.aluno_id == Aluno.id)
            .outerjoin(
                Pagamento,
                and_(
                    Pagamento.aluno_id == Aluno.id,
                    Pagamento.ano == ano,
                    Pagamento.mes == mes,
                ),
            )
            .where(Aluno.status == "active")
            .order_by(func.lower(Aluno.name))
        )
        rows = session.execute(query).all()

    resultado = []
    for aluno_id, aluno_nome, valor_plano, pagamento_id, valor_pago, data_pagamento in rows:
        resultado.append(
            {
                "aluno_id": aluno_id,
                "aluno_nome": aluno_nome,
                "valor_plano": valor_plano,
                "pago": pagamento_id is not None,
                "pagamento_id": pagamento_id,
                "valor_pago": valor_pago,
                "data_pagamento": data_pagamento,
            }
        )
    return resultado


def resumo_recebimentos_mes(ano: int, mes: int) -> Dict[str, Any]:
    """Return financial indicators of a single competence (ano/mes).

    ``recebido`` is the sum of the value actually paid by students who have
    paid. ``pendente`` is the sum of the plan value of students who have not
    paid yet. ``total_esperado`` is the sum of the plan value of every
    active student with a plan. Read-only: no log.
    """
    recebido = Decimal("0.00")
    pendente = Decimal("0.00")
    total_esperado = Decimal("0.00")

    for item in recebimentos_do_mes(ano, mes):
        total_esperado += item["valor_plano"]
        if item["pago"]:
            recebido += item["valor_pago"]
        else:
            pendente += item["valor_plano"]

    return {
        "recebido": recebido,
        "pendente": pendente,
        "total_esperado": total_esperado,
    }


def _parse_data_required(value: Optional[str]) -> datetime.date:
    """Parse a required ISO "YYYY-MM-DD" date.

    Raises :class:`ValidationError` when missing or not a valid date.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Data é obrigatória.")
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValidationError("Data inválida.")


def _parse_descricao_required(value: Optional[str]) -> str:
    """Parse a required expense description.

    Raises :class:`ValidationError` when missing.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Descrição é obrigatória.")
    return value


def _parse_categoria_despesa_optional(value: Optional[str]) -> Optional[str]:
    """Parse an optional expense category.

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when filled in
    but not one of :data:`CATEGORIAS_DESPESA`.
    """
    value = _normalize(value)
    if value is None:
        return None
    if value not in CATEGORIAS_DESPESA:
        raise ValidationError("Categoria inválida.")
    return value


def _to_despesa_dict(d: Despesa) -> Dict[str, Any]:
    """Extract a Despesa's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": d.id,
        "data": d.data,
        "descricao": d.descricao,
        "categoria": d.categoria,
        "valor": d.valor,
        "observacao": d.observacao,
        "created_at": d.created_at,
    }


def registrar_despesa(
    *,
    data: Optional[str] = None,
    descricao: Optional[str] = None,
    categoria: Optional[str] = None,
    valor: Optional[str] = None,
    observacao: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new business expense.

    Raw form values are normalized and validated before anything touches the
    database; when invalid, :class:`ValidationError` (message in Portuguese)
    is raised and nothing is persisted.
    """
    parsed_data = _parse_data_required(data)
    parsed_descricao = _parse_descricao_required(descricao)
    parsed_valor = _parse_valor_required(valor)
    parsed_categoria = _parse_categoria_despesa_optional(categoria)
    parsed_observacao = _normalize(observacao)

    with session_scope() as session:
        despesa = Despesa(
            data=parsed_data,
            descricao=parsed_descricao,
            categoria=parsed_categoria,
            valor=parsed_valor,
            observacao=parsed_observacao,
        )
        session.add(despesa)

        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(despesa)  # loads server-generated values (created_at)
        result = _to_despesa_dict(despesa)

    logger.info("Despesa registrada: id=%s valor=%s", result["id"], result["valor"])
    return result


def remover_despesa(despesa_id: int) -> bool:
    """Remove an expense.

    Returns True when an expense existed and was removed, False when there
    was none.
    """
    with session_scope() as session:
        despesa = session.get(Despesa, despesa_id)
        if despesa is None:
            return False
        session.delete(despesa)
        logger.info("Despesa removed: despesa_id=%s", despesa_id)
        return True


def get_despesa(despesa_id: int) -> Optional[Dict[str, Any]]:
    """Return an expense as a plain dict, or None when there is none."""
    with session_scope() as session:
        despesa = session.get(Despesa, despesa_id)
        if despesa is None:
            return None
        return _to_despesa_dict(despesa)


def despesas_do_mes(ano: int, mes: int) -> list:
    """Return all expenses of a given month, most recent first.

    Read-only: no log.
    """
    inicio = datetime.date(ano, mes, 1)
    fim = (
        datetime.date(ano + 1, 1, 1)
        if mes == 12
        else datetime.date(ano, mes + 1, 1)
    )
    with session_scope() as session:
        query = (
            select(Despesa)
            .where(Despesa.data >= inicio, Despesa.data < fim)
            .order_by(Despesa.data.desc(), Despesa.id.desc())
        )
        despesas = session.execute(query).scalars().all()
        return [_to_despesa_dict(d) for d in despesas]


def total_despesas_mes(ano: int, mes: int) -> Decimal:
    """Return the sum of all expense values of a given month.

    Read-only: no log.
    """
    total = Decimal("0.00")
    for item in despesas_do_mes(ano, mes):
        total += item["valor"]
    return total


def panorama_mes(ano: int, mes: int) -> Dict[str, Any]:
    """Return the consolidated financial overview of a given month (ano/mes).

    Combines the receipts summary, expenses total and overall indicators
    into a single dict: ``recebido``, ``despesas``, ``resultado`` (recebido
    minus despesas), ``a_receber``, ``mrr``, ``ticket_medio``,
    ``alunos_com_plano`` and ``sustentam`` (the active students who already
    paid this competence, sorted by paid value, highest first). Read-only:
    no log.
    """
    rec = resumo_recebimentos_mes(ano, mes)
    recebido = rec["recebido"]
    a_receber = rec["pendente"]

    despesas = total_despesas_mes(ano, mes)
    resultado = recebido - despesas

    fin = resumo_financeiro()

    sustentam = sorted(
        (
            {"aluno_nome": item["aluno_nome"], "valor_pago": item["valor_pago"]}
            for item in recebimentos_do_mes(ano, mes)
            if item["pago"]
        ),
        key=lambda item: item["valor_pago"],
        reverse=True,
    )

    return {
        "recebido": recebido,
        "despesas": despesas,
        "resultado": resultado,
        "a_receber": a_receber,
        "mrr": fin["mrr"],
        "ticket_medio": fin["ticket_medio"],
        "alunos_com_plano": fin["alunos_com_plano"],
        "sustentam": sustentam,
    }


def _add_months(ano: int, mes: int, delta: int) -> tuple:
    """Shift a (ano, mes) competence by ``delta`` months (may be negative).

    Returns the resulting (ano, mes) pair.
    """
    total = ano * 12 + (mes - 1) + delta
    return (total // 12, total % 12 + 1)


def serie_entradas_saidas(meses: int = 6) -> list:
    """Return the monthly received (Pagamento) and expense (Despesa) totals
    for the last ``meses`` months, including the current one, oldest first.

    Each item is a dict: ``ano``, ``mes``, ``recebido`` (Decimal) and
    ``despesas`` (Decimal). Read-only: no log.
    """
    hoje = datetime.date.today()
    resultado = []

    with session_scope() as session:
        for offset in range(-(meses - 1), 1):
            ano, mes = _add_months(hoje.year, hoje.month, offset)

            recebido = session.execute(
                select(func.coalesce(func.sum(Pagamento.valor), 0)).where(
                    Pagamento.ano == ano, Pagamento.mes == mes
                )
            ).scalar()

            inicio = datetime.date(ano, mes, 1)
            fim_ano, fim_mes = _add_months(ano, mes, 1)
            fim = datetime.date(fim_ano, fim_mes, 1)
            despesas = session.execute(
                select(func.coalesce(func.sum(Despesa.valor), 0)).where(
                    Despesa.data >= inicio, Despesa.data < fim
                )
            ).scalar()

            resultado.append(
                {
                    "ano": ano,
                    "mes": mes,
                    "recebido": Decimal(recebido),
                    "despesas": Decimal(despesas),
                }
            )

    return resultado


def projecao_receita(meses: int = 6) -> list:
    """Return the projected monthly recurring revenue for the next ``meses``
    months, including the current one, nearest first.

    Projection is based on active students' plans, considering each plan's
    billing cycle: a plan without ``inicio`` or ``ciclo_meses`` is assumed to
    keep recurring indefinitely; otherwise it only counts within its cycle
    window starting at ``inicio``. Each item is a dict: ``ano``, ``mes``,
    ``receita`` (Decimal) and ``alunos`` (count). Read-only: no log.
    """
    hoje = datetime.date.today()

    with session_scope() as session:
        rows = session.execute(
            select(PlanoAluno.valor, PlanoAluno.inicio, PlanoAluno.ciclo_meses)
            .join(Aluno, PlanoAluno.aluno_id == Aluno.id)
            .where(Aluno.status == "active")
        ).all()

    resultado = []
    for offset in range(meses):
        ano, mes = _add_months(hoje.year, hoje.month, offset)
        mi = ano * 12 + (mes - 1)

        receita = Decimal("0")
        alunos = 0
        for valor, inicio, ciclo_meses in rows:
            if inicio is None or ciclo_meses is None:
                ativo = True
            else:
                si = inicio.year * 12 + (inicio.month - 1)
                ativo = si <= mi < si + ciclo_meses
            if ativo:
                receita += valor
                alunos += 1

        resultado.append(
            {
                "ano": ano,
                "mes": mes,
                "receita": receita,
                "alunos": alunos,
            }
        )

    return resultado
