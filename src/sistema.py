#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema inteligente de monitoramento de missão espacial experimental.
Projeto Global Solution - FIAP ON.

Executar:
    python src/sistema.py
    python src/sistema.py data/dados.csv

O sistema lê telemetria em CSV, interpreta módulos críticos, organiza dados em
listas, fila, pilha, dicionários, hierarquia e matriz, gera alertas, calcula
previsão simples e recomenda ações técnicas priorizadas.
"""

from __future__ import annotations
import csv
import math
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Any

MODULOS = [
    "suporte_vida", "energia", "comunicacao", "habitat",
    "laboratorio", "armazenamento",
]

SEVERIDADE_VALOR = {"normal": 0, "alerta": 1, "critico": 2}

@dataclass
class Telemetria:
    horario: str
    energia_reserva: float
    consumo_kwh: float
    geracao_solar: float
    temperatura_interna: float
    temperatura_externa: float
    radiacao: float
    qualidade_comunicacao: float
    velocidade_vento: float
    modulos: Dict[str, int]
    evento: str


def bool_int(valor: str) -> int:
    """Converte texto para 0/1, aceitando inconsistências simples."""
    texto = str(valor).strip().lower()
    if texto in {"1", "true", "sim", "ok", "ativo", "normal"}:
        return 1
    if texto in {"0", "false", "nao", "não", "falha", "critico", "crítico"}:
        return 0
    # Inconsistência proposital do arquivo: valor desconhecido vira falha segura.
    return 0


def numero(valor: str, padrao: float = 0.0) -> float:
    try:
        return float(str(valor).replace(",", "."))
    except Exception:
        return padrao


def carregar_dados(caminho: str | Path) -> List[Telemetria]:
    caminho = Path(caminho)
    leituras: List[Telemetria] = []
    with caminho.open("r", encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        for linha in leitor:
            modulos = {m: bool_int(linha.get(m, "0")) for m in MODULOS}
            leituras.append(Telemetria(
                horario=linha.get("horario", "sem_horario"),
                energia_reserva=numero(linha.get("energia_reserva", 0)),
                consumo_kwh=numero(linha.get("consumo_kwh", 0)),
                geracao_solar=numero(linha.get("geracao_solar", 0)),
                temperatura_interna=numero(linha.get("temperatura_interna", 0)),
                temperatura_externa=numero(linha.get("temperatura_externa", 0)),
                radiacao=numero(linha.get("radiacao", 0)),
                qualidade_comunicacao=numero(linha.get("qualidade_comunicacao", 0)),
                velocidade_vento=numero(linha.get("velocidade_vento", 0)),
                modulos=modulos,
                evento=linha.get("evento", ""),
            ))
    if not leituras:
        raise ValueError("Arquivo de telemetria vazio.")
    return leituras


def criar_matriz(leituras: List[Telemetria]) -> List[List[float]]:
    """Matriz de leituras por horário e variável crítica."""
    return [[l.energia_reserva, l.consumo_kwh, l.geracao_solar, l.radiacao, l.qualidade_comunicacao] for l in leituras]


def criar_hierarquia() -> Dict[str, Dict[str, List[str]]]:
    """Árvore/hierarquia simplificada da missão."""
    return {
        "missao_orion_fiap": {
            "energia": ["painel_solar", "baterias", "distribuicao"],
            "habitat": ["suporte_vida", "temperatura", "radiacao"],
            "comunicacao": ["antena_principal", "canal_emergencia"],
            "carga_util": ["laboratorio", "armazenamento"],
        }
    }


def media_movel(valores: List[float], janela: int = 3) -> float:
    if not valores:
        return 0.0
    parte = valores[-janela:]
    return sum(parte) / len(parte)


def regressao_linear_prever_proximo(valores: List[float]) -> float:
    """Regressão linear simples, sem bibliotecas avançadas, para prever próximo ciclo."""
    n = len(valores)
    if n < 2:
        return valores[-1] if valores else 0.0
    xs = list(range(n))
    media_x = sum(xs) / n
    media_y = sum(valores) / n
    numerador = sum((x - media_x) * (y - media_y) for x, y in zip(xs, valores))
    denominador = sum((x - media_x) ** 2 for x in xs) or 1
    a = numerador / denominador
    b = media_y - a * media_x
    return a * n + b


def classificar(leitura: Telemetria) -> Tuple[str, List[str], str]:
    """
    Expressão booleana principal do diagnóstico:
    critico = (suporte_vida == 0) OR (energia_reserva < 25 AND consumo_kwh > geracao_solar) OR
              (qualidade_comunicacao < 45) OR (radiacao >= 7.5)
    alerta = NOT critico AND (energia_reserva < 40 OR radiacao >= 5.0 OR temperatura_interna fora de 18..27
              OR existe modulo com falha)
    """
    motivos: List[str] = []
    falhas_modulos = [m for m, v in leitura.modulos.items() if v == 0]
    energia_critica = leitura.energia_reserva < 25 and leitura.consumo_kwh > leitura.geracao_solar
    comunicacao_critica = leitura.qualidade_comunicacao < 45
    radiacao_critica = leitura.radiacao >= 7.5
    suporte_vida_falhou = leitura.modulos.get("suporte_vida", 0) == 0

    if suporte_vida_falhou:
        motivos.append("falha no suporte de vida")
    if energia_critica:
        motivos.append("energia crítica: reserva baixa e consumo acima da geração")
    if comunicacao_critica:
        motivos.append("comunicação comprometida")
    if radiacao_critica:
        motivos.append("radiação elevada")

    critico = suporte_vida_falhou or energia_critica or comunicacao_critica or radiacao_critica
    temperatura_alerta = leitura.temperatura_interna < 18 or leitura.temperatura_interna > 27
    alerta = (not critico) and (
        leitura.energia_reserva < 40 or leitura.radiacao >= 5.0 or temperatura_alerta or len(falhas_modulos) > 0
    )

    if alerta:
        if leitura.energia_reserva < 40:
            motivos.append("reserva de energia abaixo do ideal")
        if leitura.radiacao >= 5.0:
            motivos.append("radiação em faixa de atenção")
        if temperatura_alerta:
            motivos.append("temperatura interna fora da faixa segura")
        if falhas_modulos:
            motivos.append("módulos com falha: " + ", ".join(falhas_modulos))

    if critico:
        return "critico", motivos, "Acionar protocolo de emergência e priorizar sobrevivência da tripulação."
    if alerta:
        return "alerta", motivos, "Reduzir consumo, monitorar tendência e preparar contingência."
    return "normal", ["operação dentro das faixas de segurança"], "Manter monitoramento contínuo."


def gerar_alertas(leituras: List[Telemetria]) -> Tuple[List[Dict[str, Any]], deque, List[str]]:
    alertas: List[Dict[str, Any]] = []
    fila_alertas: deque = deque()       # fila: alertas pendentes por ordem de chegada/prioridade processada
    pilha_eventos: List[str] = []       # pilha: últimos eventos críticos analisados

    for leitura in leituras:
        status, motivos, recomendacao = classificar(leitura)
        if status != "normal":
            alerta = {
                "horario": leitura.horario,
                "nivel": status,
                "prioridade": SEVERIDADE_VALOR[status],
                "motivos": motivos,
                "recomendacao": recomendacao,
            }
            alertas.append(alerta)
            fila_alertas.append(alerta)
        if status == "critico" or "falha" in leitura.evento.lower() or "alerta" in leitura.evento.lower():
            pilha_eventos.append(f"{leitura.horario} - {leitura.evento} - status {status}")

    # priorização: críticos antes de alertas, preservando clareza para decisão operacional
    alertas.sort(key=lambda a: (-a["prioridade"], a["horario"]))
    return alertas, fila_alertas, pilha_eventos


def recomendacoes_finais(ultima: Telemetria, previsao_energia: float, previsao_comunicacao: float) -> List[str]:
    recs: List[str] = []
    status, motivos, _ = classificar(ultima)
    if status == "critico":
        recs.append("Prioridade 1: manter suporte de vida e comunicação de emergência ativos.")
    if previsao_energia < 30:
        recs.append("Prioridade 2: desligar laboratório e sistemas não essenciais para preservar baterias.")
    if ultima.radiacao >= 5 or any("radiação" in m for m in motivos):
        recs.append("Prioridade 3: redirecionar energia para habitat e aumentar blindagem operacional contra radiação.")
    if previsao_comunicacao < 60:
        recs.append("Prioridade 4: alternar para canal redundante e reduzir pacotes não essenciais de telemetria.")
    if not recs:
        recs.append("Manter operação nominal e revisar telemetria no próximo ciclo.")
    return recs


def imprimir_relatorio(leituras: List[Telemetria]) -> None:
    lista_energia = [l.energia_reserva for l in leituras]   # lista temporal
    lista_consumo = [l.consumo_kwh for l in leituras]
    lista_comunicacao = [l.qualidade_comunicacao for l in leituras]
    matriz = criar_matriz(leituras)
    hierarquia = criar_hierarquia()
    status_modulos = {m: leituras[-1].modulos[m] for m in MODULOS}  # dicionário/hash
    alertas, fila_alertas, pilha_eventos = gerar_alertas(leituras)
    ultima = leituras[-1]

    previsao_energia = regressao_linear_prever_proximo(lista_energia)
    previsao_comunicacao = media_movel(lista_comunicacao, janela=3)
    previsao_consumo = media_movel(lista_consumo, janela=3)
    status_atual, motivos_atual, acao_atual = classificar(ultima)
    recs = recomendacoes_finais(ultima, previsao_energia, previsao_comunicacao)

    print("=" * 72)
    print("SISTEMA INTELIGENTE DE MONITORAMENTO - MISSÃO ESPACIAL EXPERIMENTAL")
    print("=" * 72)
    print(f"Leituras processadas: {len(leituras)}")
    print(f"Último horário analisado: {ultima.horario}")
    print(f"Status operacional atual: {status_atual.upper()}")
    print("Motivos do diagnóstico: " + "; ".join(motivos_atual))
    print(f"Ação imediata: {acao_atual}")
    print("\nEstruturas utilizadas:")
    print(f"- Listas temporais: energia={lista_energia}, consumo={lista_consumo}")
    print(f"- Fila de alertas pendentes: {len(fila_alertas)} item(ns)")
    print(f"- Pilha de eventos críticos: {pilha_eventos[-3:] if pilha_eventos else []}")
    print(f"- Dicionário de status dos módulos: {status_modulos}")
    print(f"- Hierarquia da missão: {hierarquia}")
    print(f"- Matriz [energia, consumo, geração, radiação, comunicação], linhas={len(matriz)}")

    print("\nTabela simples de status dos módulos:")
    for modulo, valor in status_modulos.items():
        texto = "normal" if valor == 1 else "crítico"
        print(f"  {modulo:15s} -> {texto}")

    print("\nAlertas priorizados:")
    if not alertas:
        print("  Nenhum alerta gerado.")
    for a in alertas:
        print(f"  [{a['nivel'].upper()}] {a['horario']} - {', '.join(a['motivos'])}")
        print(f"     Recomendação: {a['recomendacao']}")

    print("\nAnálise e previsão simples:")
    print(f"- Previsão por regressão linear para reserva de energia no próximo ciclo: {previsao_energia:.1f}%")
    print(f"- Média móvel de comunicação nos últimos ciclos: {previsao_comunicacao:.1f}%")
    print(f"- Média móvel de consumo: {previsao_consumo:.1f} kWh")
    print("- A previsão influencia decisões: energia prevista baixa aumenta prioridade de economia.")

    print("\nRecomendações finais priorizadas:")
    for r in recs:
        print("  - " + r)
    print("=" * 72)


def main() -> None:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data" / "dados.csv"
    try:
        leituras = carregar_dados(caminho)
        imprimir_relatorio(leituras)
    except Exception as exc:
        print(f"Erro ao executar sistema: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
