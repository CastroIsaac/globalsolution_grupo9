#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema inteligente de monitoramento de missão espacial experimental.
Projeto Global Solution - FIAP ON.

Execução:
    python src/sistema.py
    python src/sistema.py data/dados.csv
    python src/sistema.py data/dados.csv --sem-cor

O sistema lê telemetria em CSV, interpreta módulos críticos, organiza dados em
listas, fila, pilha, dicionários, hierarquia e matriz, gera alertas, calcula
previsão simples e recomenda ações técnicas priorizadas.

Implementado sem bibliotecas externas para facilitar a execução em qualquer
ambiente com Python 3.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Tuple

MODULOS = [
    "suporte_vida",
    "energia",
    "comunicacao",
    "habitat",
    "laboratorio",
    "armazenamento",
]

COLUNAS_NUMERICAS = [
    "energia_reserva",
    "consumo_kwh",
    "geracao_solar",
    "temperatura_interna",
    "temperatura_externa",
    "radiacao",
    "qualidade_comunicacao",
    "velocidade_vento",
]

COLUNAS_OBRIGATORIAS = ["horario", *COLUNAS_NUMERICAS, *MODULOS, "evento"]
SEVERIDADE_VALOR = {"normal": 0, "alerta": 1, "critico": 2}
ANSI_RE = re.compile(r"\033\[[0-9;]*m")
USAR_CORES = True

CORES = {
    "normal": "\033[92m",    # verde
    "alerta": "\033[93m",    # amarelo
    "critico": "\033[91m",   # vermelho
    "titulo": "\033[96m",    # ciano
    "negrito": "\033[1m",
    "fim": "\033[0m",
}


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
    inconsistencias: List[str] = field(default_factory=list)


@dataclass
class Diagnostico:
    status: str
    motivos: List[str]
    acao: str
    risco: int


@dataclass
class AnaliseMissao:
    leituras: List[Telemetria]
    matriz: List[List[float]]
    hierarquia: Dict[str, Dict[str, List[str]]]
    status_modulos: Dict[str, str]
    alertas: List[Dict[str, Any]]
    fila_alertas: Deque[Dict[str, Any]]
    pilha_eventos: List[str]
    previsao_energia: float
    previsao_comunicacao: float
    previsao_consumo: float
    diagnostico_atual: Diagnostico
    recomendacoes: List[str]
    inconsistencias: List[str]


def configurar_cores(sem_cor: bool = False) -> None:
    """Desliga cores quando solicitado ou quando o terminal não suporta ANSI."""
    global USAR_CORES
    USAR_CORES = not sem_cor and "NO_COLOR" not in os.environ


def limpar_ansi(texto: str) -> str:
    return ANSI_RE.sub("", texto)


def largura_visual(texto: str) -> int:
    return len(limpar_ansi(str(texto)))


def colorir(texto: str, status: str) -> str:
    if not USAR_CORES:
        return texto
    return f"{CORES.get(status, '')}{texto}{CORES['fim']}"


def rotulo_status(status: str) -> str:
    return colorir(status.upper(), status)


def normalizar_bool(valor: str, campo: str, inconsistencias: List[str]) -> int:
    """Converte valores textuais para 0/1. Valor estranho vira falha segura."""
    texto_original = str(valor).strip()
    texto = texto_original.lower()
    verdadeiros = {"1", "true", "sim", "s", "ok", "ativo", "normal", "on"}
    falsos = {"0", "false", "nao", "não", "n", "falha", "critico", "crítico", "off"}

    if texto in verdadeiros:
        return 1
    if texto in falsos:
        return 0

    inconsistencias.append(
        f"valor inválido no módulo '{campo}' ({texto_original!r}); tratado como falha segura"
    )
    return 0


def converter_numero(valor: str, campo: str, inconsistencias: List[str], padrao: float = 0.0) -> float:
    texto_original = str(valor).strip()
    try:
        numero = float(texto_original.replace(",", "."))
    except Exception:
        inconsistencias.append(
            f"valor numérico inválido em '{campo}' ({texto_original!r}); substituído por {padrao}"
        )
        return padrao

    faixas = {
        "energia_reserva": (0, 100),
        "qualidade_comunicacao": (0, 100),
        "radiacao": (0, 20),
        "consumo_kwh": (0, 500),
        "geracao_solar": (0, 500),
    }
    if campo in faixas:
        minimo, maximo = faixas[campo]
        if not (minimo <= numero <= maximo):
            inconsistencias.append(
                f"valor fora da faixa esperada em '{campo}' ({numero}); mantido para diagnóstico"
            )
    return numero


def validar_cabecalho(cabecalho: Iterable[str] | None) -> None:
    if not cabecalho:
        raise ValueError("O CSV não possui cabeçalho.")
    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in cabecalho]
    if faltantes:
        raise ValueError("Colunas obrigatórias ausentes no CSV: " + ", ".join(faltantes))


def carregar_dados(caminho: str | Path) -> List[Telemetria]:
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    leituras: List[Telemetria] = []
    with caminho.open("r", encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        validar_cabecalho(leitor.fieldnames)

        for numero_linha, linha in enumerate(leitor, start=2):
            inconsistencias: List[str] = []
            modulos = {
                modulo: normalizar_bool(linha.get(modulo, "0"), modulo, inconsistencias)
                for modulo in MODULOS
            }
            valores = {
                campo: converter_numero(linha.get(campo, "0"), campo, inconsistencias)
                for campo in COLUNAS_NUMERICAS
            }
            if not linha.get("horario"):
                inconsistencias.append("horário vazio")

            leituras.append(
                Telemetria(
                    horario=linha.get("horario", f"linha_{numero_linha}"),
                    energia_reserva=valores["energia_reserva"],
                    consumo_kwh=valores["consumo_kwh"],
                    geracao_solar=valores["geracao_solar"],
                    temperatura_interna=valores["temperatura_interna"],
                    temperatura_externa=valores["temperatura_externa"],
                    radiacao=valores["radiacao"],
                    qualidade_comunicacao=valores["qualidade_comunicacao"],
                    velocidade_vento=valores["velocidade_vento"],
                    modulos=modulos,
                    evento=linha.get("evento", ""),
                    inconsistencias=[f"linha {numero_linha}: {i}" for i in inconsistencias],
                )
            )

    if not leituras:
        raise ValueError("Arquivo de telemetria vazio.")
    return leituras


def criar_matriz(leituras: List[Telemetria]) -> List[List[float]]:
    return [
        [
            l.energia_reserva,
            l.consumo_kwh,
            l.geracao_solar,
            l.radiacao,
            l.qualidade_comunicacao,
        ]
        for l in leituras
    ]


def criar_hierarquia() -> Dict[str, Dict[str, List[str]]]:
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
    n = len(valores)
    if n < 2:
        return valores[-1] if valores else 0.0

    xs = list(range(n))
    media_x = sum(xs) / n
    media_y = sum(valores) / n
    numerador = sum((x - media_x) * (y - media_y) for x, y in zip(xs, valores))
    denominador = sum((x - media_x) ** 2 for x in xs) or 1.0
    coef_angular = numerador / denominador
    coef_linear = media_y - coef_angular * media_x
    return coef_angular * n + coef_linear


def tendencia(valores: List[float]) -> str:
    if len(valores) < 2:
        return "estável"
    diferenca = valores[-1] - valores[0]
    if diferenca > 3:
        return "subindo"
    if diferenca < -3:
        return "caindo"
    return "estável"


def classificar(leitura: Telemetria) -> Diagnostico:
    """
    Expressão booleana principal do diagnóstico:

    critico = suporte_vida_falhou OR
              (energia_reserva < 25 AND consumo_kwh > geracao_solar) OR
              qualidade_comunicacao < 45 OR
              radiacao >= 7.5

    alerta = NOT critico AND
             (energia_reserva < 40 OR radiacao >= 5.0 OR temperatura_interna fora de 18..27
              OR existe módulo com falha OR existem inconsistências nos dados)
    """
    motivos: List[str] = []
    risco = 0

    falhas_modulos = [m for m, v in leitura.modulos.items() if v == 0]
    suporte_vida_falhou = leitura.modulos.get("suporte_vida", 0) == 0
    energia_critica = leitura.energia_reserva < 25 and leitura.consumo_kwh > leitura.geracao_solar
    comunicacao_critica = leitura.qualidade_comunicacao < 45
    radiacao_critica = leitura.radiacao >= 7.5

    if suporte_vida_falhou:
        motivos.append("falha no suporte de vida")
        risco += 35
    if energia_critica:
        motivos.append("energia crítica: reserva baixa e consumo acima da geração")
        risco += 30
    if comunicacao_critica:
        motivos.append("comunicação comprometida")
        risco += 20
    if radiacao_critica:
        motivos.append("radiação elevada")
        risco += 25

    critico = suporte_vida_falhou or energia_critica or comunicacao_critica or radiacao_critica

    temperatura_alerta = leitura.temperatura_interna < 18 or leitura.temperatura_interna > 27
    energia_alerta = leitura.energia_reserva < 40
    radiacao_alerta = leitura.radiacao >= 5.0
    falha_nao_critica = len(falhas_modulos) > 0
    dados_inconsistentes = len(leitura.inconsistencias) > 0

    alerta = (not critico) and (
        energia_alerta or radiacao_alerta or temperatura_alerta or falha_nao_critica or dados_inconsistentes
    )

    if alerta:
        if energia_alerta:
            motivos.append("reserva de energia abaixo do ideal")
            risco += 15
        if radiacao_alerta:
            motivos.append("radiação em faixa de atenção")
            risco += 12
        if temperatura_alerta:
            motivos.append("temperatura interna fora da faixa segura")
            risco += 10
        if falha_nao_critica:
            motivos.append("módulos com falha: " + ", ".join(falhas_modulos))
            risco += 10
        if dados_inconsistentes:
            motivos.append("inconsistência detectada nos dados de telemetria")
            risco += 8

    if critico:
        return Diagnostico(
            status="critico",
            motivos=motivos,
            acao="Acionar protocolo de emergência e priorizar sobrevivência da tripulação.",
            risco=min(max(risco, 75), 100),
        )
    if alerta:
        return Diagnostico(
            status="alerta",
            motivos=motivos,
            acao="Reduzir consumo, monitorar tendência e preparar contingência.",
            risco=min(max(risco, 20), 70),
        )
    return Diagnostico(
        status="normal",
        motivos=["operação dentro das faixas de segurança"],
        acao="Manter monitoramento contínuo.",
        risco=min(risco, 15),
    )


def gerar_alertas(leituras: List[Telemetria]) -> Tuple[List[Dict[str, Any]], Deque[Dict[str, Any]], List[str]]:
    alertas: List[Dict[str, Any]] = []
    fila_alertas: Deque[Dict[str, Any]] = deque()
    pilha_eventos: List[str] = []

    for leitura in leituras:
        diag = classificar(leitura)
        if diag.status != "normal":
            alerta = {
                "horario": leitura.horario,
                "nivel": diag.status,
                "prioridade": SEVERIDADE_VALOR[diag.status],
                "risco": diag.risco,
                "motivos": diag.motivos,
                "recomendacao": diag.acao,
            }
            alertas.append(alerta)
            fila_alertas.append(alerta)

        evento_texto = leitura.evento.lower()
        if diag.status == "critico" or "falha" in evento_texto or "alerta" in evento_texto:
            pilha_eventos.append(f"{leitura.horario} - {leitura.evento} - status {diag.status}")

    alertas.sort(key=lambda a: (-a["prioridade"], -a["risco"], a["horario"]))
    return alertas, fila_alertas, pilha_eventos


def diagnosticar_status_modulos(leituras: List[Telemetria]) -> Dict[str, str]:
    status: Dict[str, str] = {}
    ultima = leituras[-1]
    for modulo in MODULOS:
        falhou_alguma_vez = any(l.modulos.get(modulo, 1) == 0 for l in leituras)
        falha_atual = ultima.modulos.get(modulo, 1) == 0
        if falha_atual:
            status[modulo] = "critico"
        elif falhou_alguma_vez:
            status[modulo] = "alerta"
        else:
            status[modulo] = "normal"
    return status


def recomendacoes_finais(ultima: Telemetria, previsao_energia: float, previsao_comunicacao: float) -> List[str]:
    recs: List[str] = []
    diag = classificar(ultima)

    if diag.status == "critico":
        recs.append("Prioridade 1: manter suporte de vida e comunicação de emergência ativos.")
    if previsao_energia < 30:
        recs.append("Prioridade 2: desligar laboratório e sistemas não essenciais para preservar baterias.")
    if ultima.radiacao >= 5 or any("radiação" in m for m in diag.motivos):
        recs.append("Prioridade 3: redirecionar energia para habitat e aumentar blindagem contra radiação.")
    if previsao_comunicacao < 60:
        recs.append("Prioridade 4: alternar para canal redundante e reduzir pacotes não essenciais de telemetria.")
    if ultima.energia_reserva < 25 and ultima.consumo_kwh > ultima.geracao_solar:
        recs.append("Prioridade 5: limitar consumo por ciclo até a geração superar a demanda.")
    if ultima.inconsistencias:
        recs.append("Prioridade 6: validar sensores inconsistentes antes de tomar decisões irreversíveis.")
    if not recs:
        recs.append("Manter operação nominal e revisar telemetria no próximo ciclo.")
    return recs


def analisar_missao(leituras: List[Telemetria]) -> AnaliseMissao:
    energia = [l.energia_reserva for l in leituras]
    consumo = [l.consumo_kwh for l in leituras]
    comunicacao = [l.qualidade_comunicacao for l in leituras]

    previsao_energia = regressao_linear_prever_proximo(energia)
    previsao_comunicacao = media_movel(comunicacao, janela=3)
    previsao_consumo = media_movel(consumo, janela=3)
    alertas, fila_alertas, pilha_eventos = gerar_alertas(leituras)

    return AnaliseMissao(
        leituras=leituras,
        matriz=criar_matriz(leituras),
        hierarquia=criar_hierarquia(),
        status_modulos=diagnosticar_status_modulos(leituras),
        alertas=alertas,
        fila_alertas=fila_alertas,
        pilha_eventos=pilha_eventos,
        previsao_energia=previsao_energia,
        previsao_comunicacao=previsao_comunicacao,
        previsao_consumo=previsao_consumo,
        diagnostico_atual=classificar(leituras[-1]),
        recomendacoes=recomendacoes_finais(leituras[-1], previsao_energia, previsao_comunicacao),
        inconsistencias=[i for leitura in leituras for i in leitura.inconsistencias],
    )


def imprimir_separador(larguras: List[int]) -> None:
    print("+" + "+".join("-" * (l + 2) for l in larguras) + "+")


def imprimir_linha(colunas: List[str], larguras: List[int]) -> None:
    celulas = []
    for conteudo, largura in zip(colunas, larguras):
        texto = str(conteudo)
        espacos = max(0, largura - largura_visual(texto))
        celulas.append(texto + " " * espacos)
    print("| " + " | ".join(celulas) + " |")


def imprimir_tabela(titulos: List[str], linhas: List[List[str]]) -> None:
    larguras = [largura_visual(t) for t in titulos]
    for linha in linhas:
        for i, valor in enumerate(linha):
            larguras[i] = max(larguras[i], largura_visual(valor))
    imprimir_separador(larguras)
    imprimir_linha(titulos, larguras)
    imprimir_separador(larguras)
    for linha in linhas:
        imprimir_linha(linha, larguras)
    imprimir_separador(larguras)


def imprimir_dashboard(analise: AnaliseMissao) -> None:
    ultima = analise.leituras[-1]
    diag = analise.diagnostico_atual
    linhas = [
        ["Status geral", rotulo_status(diag.status)],
        ["Índice de risco", f"{diag.risco}/100"],
        ["Energia atual", f"{ultima.energia_reserva:.1f}%"],
        ["Energia prevista", f"{analise.previsao_energia:.1f}%"],
        ["Consumo médio", f"{analise.previsao_consumo:.1f} kWh"],
        ["Comunicação média", f"{analise.previsao_comunicacao:.1f}%"],
        ["Radiação atual", f"{ultima.radiacao:.1f}"],
        ["Alertas ativos", str(len(analise.alertas))],
    ]
    print("\n" + colorir("RESUMO EXECUTIVO DA MISSÃO", "titulo"))
    imprimir_tabela(["Indicador", "Valor"], linhas)


def imprimir_relatorio(leituras: List[Telemetria]) -> None:
    analise = analisar_missao(leituras)
    ultima = leituras[-1]
    energia = [l.energia_reserva for l in leituras]
    consumo = [l.consumo_kwh for l in leituras]
    comunicacao = [l.qualidade_comunicacao for l in leituras]
    diag = analise.diagnostico_atual

    print("=" * 78)
    print(colorir("SISTEMA INTELIGENTE DE MONITORAMENTO - MISSÃO ESPACIAL EXPERIMENTAL", "titulo"))
    print("=" * 78)
    print(f"Leituras processadas: {len(leituras)}")
    print(f"Último horário analisado: {ultima.horario}")
    print(f"Status operacional atual: {rotulo_status(diag.status)}")
    print("Motivos do diagnóstico: " + "; ".join(diag.motivos))
    print(f"Ação imediata: {diag.acao}")

    imprimir_dashboard(analise)

    print("\nEstruturas de dados utilizadas:")
    print(f"- Listas temporais: energia={energia}, consumo={consumo}, comunicação={comunicacao}")
    print(f"- Fila de alertas pendentes: {len(analise.fila_alertas)} item(ns)")
    print(f"- Pilha de eventos críticos (últimos 3): {analise.pilha_eventos[-3:] if analise.pilha_eventos else []}")
    print(f"- Dicionário/hash de status dos módulos: {analise.status_modulos}")
    print(f"- Hierarquia/árvore da missão: {analise.hierarquia}")
    print(f"- Matriz [energia, consumo, geração, radiação, comunicação], linhas={len(analise.matriz)}")

    print("\nTabela de status dos módulos:")
    linhas_modulos = []
    for modulo, status_modulo in analise.status_modulos.items():
        if status_modulo == "critico":
            interpretacao = "falha na última leitura"
        elif status_modulo == "alerta":
            interpretacao = "falhou e foi recuperado"
        else:
            interpretacao = "sem falhas registradas"
        linhas_modulos.append([modulo, rotulo_status(status_modulo), interpretacao])
    imprimir_tabela(["Módulo", "Status", "Interpretação"], linhas_modulos)

    print("\nAlertas priorizados:")
    if not analise.alertas:
        print("  Nenhum alerta gerado.")
    for alerta in analise.alertas:
        nivel = alerta["nivel"]
        print(
            f"  [{rotulo_status(nivel)} | risco {alerta['risco']}/100] "
            f"{alerta['horario']} - {', '.join(alerta['motivos'])}"
        )
        print(f"     Recomendação: {alerta['recomendacao']}")

    if analise.inconsistencias:
        print("\nInconsistências detectadas nos dados:")
        for item in analise.inconsistencias:
            print(f"  - {item}")

    print("\nAnálise e previsão simples:")
    print(f"- Tendência da energia na missão: {tendencia(energia)}")
    print(f"- Tendência da comunicação na missão: {tendencia(comunicacao)}")
    print(f"- Previsão por regressão linear para reserva de energia no próximo ciclo: {analise.previsao_energia:.1f}%")
    print(f"- Média móvel de comunicação nos últimos ciclos: {analise.previsao_comunicacao:.1f}%")
    print(f"- Média móvel de consumo: {analise.previsao_consumo:.1f} kWh")
    print("- Decisão automática: energia prevista baixa aumenta prioridade de economia e corte de cargas não essenciais.")

    print("\nRecomendações finais priorizadas:")
    for rec in analise.recomendacoes:
        print("  - " + rec)
    print("=" * 78)


def criar_parser() -> argparse.ArgumentParser:
    raiz_projeto = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Sistema inteligente de monitoramento de missão espacial experimental."
    )
    parser.add_argument(
        "csv",
        nargs="?",
        default=str(raiz_projeto / "data" / "dados.csv"),
        help="caminho do arquivo CSV de telemetria",
    )
    parser.add_argument(
        "--sem-cor",
        action="store_true",
        help="exibe a saída sem cores ANSI",
    )
    return parser


def main() -> None:
    parser = criar_parser()
    args = parser.parse_args()
    configurar_cores(args.sem_cor)

    try:
        leituras = carregar_dados(args.csv)
        imprimir_relatorio(leituras)
    except Exception as exc:
        print(f"Erro ao executar sistema: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
