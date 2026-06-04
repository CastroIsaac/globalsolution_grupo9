# Sistema Inteligente de Monitoramento - Missão Espacial Experimental

## Equipe
- Nome da equipe: **Socorro.py**
- Integrantes/RMs:
**Isaac Aurélio de Freitas Castro | RM 571175**
**Julia Guimarães | RM 572241**
**Samirah Pinotti Deranian | RM 573375**
**Luiz Pedro Pereira Duarte | RM 568970**

## Resumo do problema
Missões espaciais dependem de monitoramento contínuo para garantir segurança da tripulação, eficiência energética, comunicação e proteção contra eventos ambientais. Este projeto simula uma missão espacial experimental e interpreta dados de telemetria para identificar situações normais, de alerta ou críticas.

## Cenário analisado
A missão monitora suporte de vida, energia, comunicação, habitat, laboratório e armazenamento. O arquivo `data/dados.csv` contém leituras em 8 horários, incluindo geração/consumo de energia, reserva energética, radiação, comunicação, temperatura, vento, eventos operacionais e uma inconsistência proposital para testar o diagnóstico.

## Estruturas de dados usadas e justificativa
- **Listas:** armazenam séries temporais de energia, consumo e comunicação.
- **Fila:** organiza alertas pendentes para atendimento operacional.
- **Pilha:** registra os eventos críticos mais recentes analisados.
- **Dicionários/tabela hash:** permitem acessar rapidamente o status dos módulos pelo nome.
- **Hierarquia/árvore:** representa subsistemas da missão, como energia, habitat, comunicação e carga útil.
- **Matriz/lista de listas:** representa leituras por horário e variável crítica.

## Regras lógicas principais
Expressão booleana principal do diagnóstico:

```text
critico = (suporte_vida == 0) OR
          (energia_reserva < 25 AND consumo_kwh > geracao_solar) OR
          (qualidade_comunicacao < 45) OR
          (radiacao >= 7.5)

alerta = NOT critico AND
         (energia_reserva < 40 OR radiacao >= 5.0 OR temperatura_interna fora de 18..27 OR existe modulo com falha)
```

As regras usam `IF`, `ELIF`, `ELSE`, `AND`, `OR` e `NOT`. Uma situação é crítica quando ameaça sobrevivência, energia mínima, comunicação ou proteção contra radiação. Uma situação é alerta quando ainda não é crítica, mas já exige prevenção.

## Técnica de previsão utilizada e resultado
O sistema usa **regressão linear simples** para prever a reserva de energia do próximo ciclo e **média móvel** para comunicação e consumo. Na base simulada, a tendência indica queda na energia, o que gera recomendação de economia e desligamento de sistemas não essenciais quando a previsão fica baixa.

## Como executar
No terminal, dentro da pasta do projeto:

```bash
python src/sistema.py
```

Ou informando outro arquivo CSV:

```bash
python src/sistema.py data/dados.csv
```

## Exemplo de entrada
Trecho do arquivo `data/dados.csv`:

```csv
horario,energia_reserva,consumo_kwh,geracao_solar,radiacao,qualidade_comunicacao,suporte_vida,energia,comunicacao
2026-05-26 04:00,24,81,20,7.6,43,1,1,0
```

## Exemplo de saída esperada
```text
Status operacional atual: CRITICO
Motivos do diagnóstico: energia crítica; comunicação comprometida; radiação elevada
Previsão por regressão linear para reserva de energia no próximo ciclo: valor baixo
Recomendações finais priorizadas:
- manter suporte de vida e comunicação de emergência ativos
- desligar laboratório e sistemas não essenciais
- redirecionar energia para habitat
```

## Recomendações geradas pelo sistema
- Manter suporte de vida e comunicação de emergência ativos.
- Desligar laboratório e sistemas não essenciais quando a energia prevista estiver baixa.
- Redirecionar energia para habitat e carregamento das baterias.
- Usar canal redundante caso a comunicação caia.

## Link do vídeo no YouTube
Preencher após publicar como **Não Listado**:

```text
https://youtu.be/COLE_O_LINK_AQUI
```
