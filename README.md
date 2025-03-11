# pytraders

Este pacote fornece ferramentas para operações de backtest no mercado de capitais.
Seu principal diferencial é facilitar backtests de estratégias de negociação sobre ativos que compõem um dado índice da bolsa de valores B3.

## Instalação

No google colaboratory:
```python
!pip install git+https://github.com/rodigosch/pytraders.git
```

## Uso

### Importe a classe `Carteira`

```python
from pytraders import Carteira
```

### Instancie o objeto `bt_carteira` da classe `Carteira` 
```python
INDICE_B3 = 'ibxx'
DATA_INICIO = "2024-01-01"
DATA_FIM = '2024-05-10'
bt_carteira = Carteira(INDICE_B3, DATA_INICIO, DATA_FIM)
```

#### Índices B3

| Código | Índice| Composição|
|---|---|:---|
| IBOV | Índice Bovespa|É o principal indicador de desempenho das ações negociadas na B3 e reúne as empresas mais importantes do mercado de capitais brasileiro|
| IBXX | Índice IBrX 100| 100 ativos de maior negociabilidade e representatividade do mercado de ações brasileiro.|
| IBXL | Índice IBrX 50|50 ativos de maior negociabilidade e representatividade do mercado de ações brasileiro.|
| IBRA | Índice Brasil Amplo|O objetivo do IBrA é ser o indicador do desempenho médio das cotações de todos os ativos negociados no mercado a vista (lote-padrão) da B3 que atendam a critérios mínimos de liquidez e presença em pregão, de forma a oferecer uma visão ampla do mercado acionário.|
| IFNC | Índice Financeiro|ativos de maior negociabilidade e representatividade dos setores de intermediários financeiros, serviços financeiros diversos, previdência e seguros.|
| ICON | Índice de Consumo|ativos de maior negociabilidade e representatividade dos setores de consumo cíclico, consumo não cíclico e saúde.|
| IEEX | Índice de Energia Elétrica|ativos de maior negociabilidade e representatividade do setor de energia elétrica.|
| IFIX | Índice de Fundos Imobiliários |fundos imobiliários negociados nos mercados de bolsa e de balcão organizado da B3.|
| IFIL | Índice de Fundos Imobiliários de Alta Liquidez |fundos imobiliários mais líquidos negociados nos mercados de bolsa e de balcão organizado da B3.|
| IMAT | Índice de Materiais Básicos |ativos de maior negociabilidade e representatividade do setor de materiais básicos.|
| IDIV | Índice Dividendos |ativos que se destacaram em termos de remuneração dos investidores, sob a forma de dividendos e juros sobre o capital próprio.|
| INDX | Índice do Setor Industrial |ativos de maior negociabilidade e representatividade dos setores da atividade industrial compreendidos por materiais básicos, bens industriais, consumo cíclico, consumo não cíclico, tecnologia da informação e saúde.|
| IMOB | Índice Imobiliário | ativos de maior negociabilidade e representatividade dos setores da atividade imobiliária compreendidos por exploração de imóveis e construção civil.|
| MLCX | Índice MidLarge Cap |ativos de uma carteira composta pelas empresas de maior capitalização.|
| SMLL | Índice Small Cap| empresas de menor capitalização.|
| UTIL | Índice Utilidade Pública |ativos de maior negociabilidade e representatividade do setor de utilidade pública (energia elétrica, água e saneamento e gás).|
| IVBX |Índice Valor| empresas bem conceituadas pelos investidores.|



### Verifique a lista dos ativos obtidos do site da B3
```python
bt_carteira.ativos
```

### Verifique as cotações obtidas do yahoo finance
```python
bt_carteira.cotacoes
```

### Se necessário, recarregue as cotações sem releitura dos ativos da B3
```python
DATA_INICIO = "2020-01-01"
DATA_FIM = '2023-05-10'
bt_carteira.reload_cotacoes(DATA_INICIO, DATA_FIM)
```

### Crei suas variáveis a partir das cotações
```python
# Pacote 'TA' oferece funções prontas de análise técnica
# https://technical-analysis-library-in-python.readthedocs.io/en/latest/
# Bastar importar as classes pois o pytraders já instalou 
from ta.volatility import DonchianChannel, AverageTrueRange
from ta.trend import SMAIndicator

# Cópia de novo dataframe remodelado para facilitar a criação das variáveis
df = bt_carteira.cotacoes.copy().swaplevel(axis=1)

# Obtém os valores únicos do nível mais externo (nível 0), a fim de montar uma lista dos tickers
tickers = df.columns.get_level_values(0).unique()

# Dicionário para armazenar os dados das novas colunas a serem criadas
novas_colunas = {}

# Iterando sobre os tickers (ativos)
for ativo in tickers:
  # dados básicos
  close = df[ativo]['Close']
  open = df[ativo]['Open']
  high = df[ativo]['High']
  low = df[ativo]['Low']
  volumeFin = df[ativo]['Volume'] * close
  close_ontem = close.shift(1)
  novas_colunas[(ativo, 'close_ontem')] = close_ontem
  open_amanha = open.shift(-1)
  datetime = df[ativo].index

  # data da abertura do candle
  novas_colunas[(ativo, 'datetime')] = datetime
  # Atr atual é menor que o atr de 20?
  atr_atual = AverageTrueRange(high, low, close, window=2).average_true_range()
  atr_media = SMAIndicator(atr_atual, 20).sma_indicator()
  novas_colunas[(ativo, 'atr_recente_calmo')] = np.where((atr_atual <= atr_media), 1, 0)

# Adicionar todas as novas colunas ao DataFrame original de uma só vez
novas_colunas_df = pd.DataFrame(novas_colunas, index=df.index)
df = pd.concat([df, novas_colunas_df], axis=1)
```

### Faça o setup da sua estratégia
```python
CAPITAL_INICIAL = 100000 
DIVERSIFICACAO_MAXIMA = 10
REINVESTIR_LUCROS = True
TAXA_CUSTO_OPERACIONAL = 0.0004 #0.04%
bt_carteira.setup_backtest(CAPITAL_INICIAL, DIVERSIFICACAO_MAXIMA, REINVESTIR_LUCROS, TAXA_CUSTO_OPERACIONAL, df) # df é o dataframe que você gerou no passo anterior onde foram criadas as variáveis de análise
```

### Negociação
```python
# Para cada pregão
for pregao in bt_carteira.pregoes.index:
  # Para cada ativo analisado
  for ativo in bt_carteira.ativos.itertuples():
    # Variáveis a serem analisadas
    aberturaAmanha = bt_carteira.pregoes.at[pregao, (ativo.Código, 'aberturaAmanha')]
    abertura = bt_carteira.pregoes.at[pregao, (ativo.Código, 'Open')]
    minima_ontem = bt_carteira.pregoes.at[pregao, (ativo.Código, 'minima_ontem')]
    maxima_ontem = bt_carteira.pregoes.at[pregao, (ativo.Código, 'maxima_ontem')]
    fechamento = bt_carteira.pregoes.at[pregao, (ativo.Código, 'Close')]
    fechamento_ontem = bt_carteira.pregoes.at[pregao, (ativo.Código, 'fechamento_ontem')]
    sma_close_ontem = bt_carteira.pregoes.at[pregao, (ativo.Código, 'sma_close_ontem')]
    maxima = bt_carteira.pregoes.at[pregao, (ativo.Código, 'High')]
    if (DONCHIAN):
      dcHighOntemEntrada = bt_carteira.pregoes.at[pregao, (ativo.Código, 'dcHighOntemEntrada')]
      dcLowOntemEntrada = bt_carteira.pregoes.at[pregao, (ativo.Código, 'dcLowOntemEntrada')]
      dcHighOntemSaida = bt_carteira.pregoes.at[pregao, (ativo.Código, 'dcHighOntemSaida')]
      dcLowOntemSaida = bt_carteira.pregoes.at[pregao, (ativo.Código, 'dcLowOntemSaida')]

    # Se faltam dados para algum ativo, desconsidera-o
    if (math.isnan(aberturaAmanha) or aberturaAmanha == 0 or math.isnan(fechamento) or math.isnan(fechamento_ontem)):
      continue
    if (DONCHIAN and (math.isnan(dcHighOntemEntrada) or math.isnan(dcLowOntemEntrada) or math.isnan(dcHighOntemSaida) or math.isnan(dcLowOntemSaida))):
      continue

    # Análise de eventual posição aberta no ativo
    if (bt_carteira.temPosicaoAberta(ativo.Código)):
      temSinalSaida = False
      pregao_saida = pregao
      stopou = False
      if (SAIR_DONCHIAN):
        # Analisa perda do canal inferior donchian para saída da posição
        if ((fechamento < dcLowOntemSaida) and (fechamento_ontem > dcLowOntemSaida)):
          temSinalSaida = True

      if (temSinalSaida):
        resultadoTrade = bt_carteira.fecharPosicao(pregao_saida, ativo.Código, precoNegociacao)

    if (not bt_carteira.temPosicaoAberta(ativo.Código)):
      # Não tem posição aberta no ativo
      temSinalEntrada = False

      # Verifica oportunidades de entrada
      if (ENTRAR_DONCHIAN):
        if ((fechamento > dcHighOntemEntrada) and (fechamento_ontem < dcHighOntemEntrada)):
          temSinalEntrada = True

      if (FILTRAR_SMA):
        if (abertura < sma_close_ontem):
          temSinalEntrada = False

      # Em caso de sinal de entrada, abre posição se houver condições financeiras
      if (temSinalEntrada):
        volumeOperacao = bt_carteira.getVolumeOperacao(precoNegociacao)
        if (volumeOperacao > 0 and bt_carteira.temSaldoLiquido(volumeOperacao * precoNegociacao)):
          if (bt_carteira.getQuantidadePosicoesAbertas() < DIVERSIFICACAO_MAXIMA):
            stopLoss = NaN
            stopGain = NaN
            if (SAIR_STOP_ATR):
              stopLoss = lower_band
            bt_carteira.abrirPosicao(pregao, ativo.Código, 'BUY', volumeOperacao, precoNegociacao, observacao, stopLoss, stopGain)

  # Atualiza patrimônio
  bt_carteira.atualizarPatrimonio(pregao, 'INC_CAPITAL', bt_carteira.getResultadoPosicoesAbertas(pregao))

bt_carteira.arredondar_casas_decimais(2)
```

### Verificando as operações
```python
from google.colab.data_table import DataTable
DataTable(bt_carteira.operacoes)
```

### Verificando as posições
```python
from google.colab.data_table import DataTable
DataTable(bt_carteira.posicoes)
```

### Verificando o patrimônio
```python
from google.colab.data_table import DataTable
DataTable(bt_carteira.patrimonio)
```

### Verificando as métricas dos resultados
```python
TAXA_LIVRE_RISCO_AA = 0.1325 # Taxa livre de risco ao ano (necessário para índice de sharpe)
bt_carteira.getMetricas('YE', taxa_livre_risco_aa = TAXA_LIVRE_RISCO_AA) 'YE' solicita análise de CAGR ao ano, 'M' solicita ao mês
```

### Verificando a rentabilidade média ano a ano ou mês a mês
```python
from google.colab.data_table import DataTable
rentabilidade_media = bt_carteira.get_rentabilidade_media('M') # 'M' solicita análise mês a mês, 'YE' solicita ano a ano
DataTable(rentabilidade_media[['capital', 'retorno']])
```

### Verificando o gráfico da curva de capital
```python
bt_carteira.plotar_curva_capital(plot_liquido=False) # Opção de plotar ou não a linha do saldo líquido ao longo do tempo
```
