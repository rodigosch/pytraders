from datetime import datetime
import yfinance as yf
import pandas as pd
from time import sleep
import numpy as np
from matplotlib import pyplot as plt
from selenium.webdriver.common.by import By
import os
from selenium import webdriver
import chromedriver_autoinstaller
from collections import deque

class Carteira:
  def __init__(self, indice_b3, data_inicio, data_fim):
    chromedriver_autoinstaller.install()
    self.indice_b3 = indice_b3
    self.data_inicio = data_inicio
    self.data_fim = data_fim
    self.patrimonio = None
    self.posicoes = None
    self.operacoes = None
    self.pregoes = None
    self.diversificacao_maxima = None
    self.reinvestir_lucros = None
    self.custo_operacional = None

    # >>> ADICIONAR ESTAS LINHAS PARA O FILTRO MM5:
    self.filtro_mm5_ativo = False
    self.mm5_criterio = 'crescente'
    self.mm5_historico_diario = []
    self.mm5_capital_inicio_dia = None
    self.mm5_dia_atual = None
    self.mm5_ultimos_5_dias = deque(maxlen=5)
    self.mm5_valor = None
    self.mm5_valor_anterior = None
    self.mm5_pode_operar_hoje = True
    self.mm5_operacoes_dia = 0


  def __init_carteira(self):
    # Dataframe da evolução do patrimônio
    # liquido: valor em conta corrente disponível para compras
    # saldo: demonstra evolução do capital considerando somente o saldo de posições fechadas
    # capital: demonstra evolução do capital considerando também a cotação das posições abertas
    patrimonio = pd.DataFrame(columns=['data', 'liquido', 'saldo', 'capital'])
    # Dataframe das posições
    posicoes = pd.DataFrame(columns=('ativo', 'tipo', 'volume', 'dataEntrada', 'precoEntrada', 'dataSaida', 'precoSaida', 'resultado', 'retorno', 'forcaRelativa', 'stopLoss', 'stopGain'))
    # Dataframe das operações
    operacoes = pd.DataFrame(columns=['data', 'ativo', 'tipo', 'direcao', 'volume', 'preco', 'custo'])
    return patrimonio, posicoes, operacoes
  
  def setup_backtest(self, capital_inicial, diversificacao_maxima, reinvestir_lucros, taxa_custo_operacional, pregoes):
    self.patrimonio, self.posicoes, self.operacoes = self.__init_carteira()
    self.atualizarPatrimonio(pd.to_datetime(self.data_inicio), 'DEPOSIT', capital_inicial)
    self.pregoes = pregoes
    self.diversificacao_maxima = diversificacao_maxima
    self.reinvestir_lucros = reinvestir_lucros
    self.taxa_custo_operacional = taxa_custo_operacional

  # Recebe um índice B3 e retorna um dataframe dos ativos que o compõe
  def __load_ativos(self, espera=8):
    # 1. Define o diretório atual como local de download
    download_dir = os.getcwd() # No Colab, isso geralmente é '/content'

    # 2. Configura as opções
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    prefs = {
        "download.default_directory": download_dir,  # Onde salvar
        "download.prompt_for_download": False,       # Não perguntar onde salvar
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True                 # Necessário para alguns tipos de arquivo
    }
    options.add_experimental_option("prefs", prefs)
    # open it, go to a website, and get results
    wd = webdriver.Chrome(options=options)
    #wd.get("https://www.google.com")
    #print(wd.page_source)  # results
    # divs = wd.find_elements_by_css_selector('div')
    url = f'https://sistemaswebb3-listados.b3.com.br/indexPage/day/{self.indice_b3.upper()}?language=pt-br'
    wd.get(url)
    sleep(espera)

    wd.find_element(By.ID, 'segment').send_keys("Setor de Atuação")
    sleep(espera)

    wd.find_element(By.LINK_TEXT, "Download").click()
    sleep(espera)

    #arquivos = !ls -1t /content/*.csv
    # Liste arquivos diretamente com os.path
    arquivos = sorted([f for f in os.listdir('/content') if f.endswith('.csv')], key=lambda x: os.path.getmtime(os.path.join('/content', x)), reverse=True)
    if arquivos:
      arquivo_csv = os.path.join('/content', arquivos[0])
      return pd.read_csv(arquivo_csv, sep=';', encoding='ISO-8859-1', skipfooter=2, engine='python', thousands='.', decimal=',', header=1, index_col=False)
    else:
      raise FileNotFoundError("Nenhum arquivo CSV encontrado no diretório '/content'.")

  def ler_tickers(self):
    self.ativos = self.__load_ativos(5)

  def reler_tickers_e_cotacoes(self, indice_b3):
    self.indice_b3 = indice_b3
    self.ativos = self.__load_ativos(5)
    self.cotacoes = self.__load_cotacoes()

  def __load_cotacoes(self):
    # Gera códigos de ativos no padrão yfinance
    tickers = [ticker + '.SA' for ticker in self.ativos['Código']]
    # Download das cotações
    cotacoes = yf.download(
        tickers = tickers,        # Símbolos das ações (separados por espaço, se for mais de um)
        start = self.data_inicio, # Data inicial
        end = self.data_fim,      # Data final
        interval = "1d",          # Intervalo (e.g., '1d', '1wk', '1mo')
        #group_by=None, #"ticker",# Agrupar por 'ticker' (útil para múltiplos ativos)
        auto_adjust = True,       # Ajusta automaticamente preços para desdobramentos e dividendos
        threads = True,           # Faz download de múltiplos ativos em paralelo
        progress = True           # Mostra barra de progresso durante o download
    )
    # Dicionário mapeando os códigos yfinance em código B3
    dict_tickers = dict(zip(tickers, self.ativos['Código']))
    # Renomeia as colunas com códigos de ativo B3
    return cotacoes.rename(columns = dict_tickers)
  
  def ler_cotacoes(self):
    self.cotacoes = self.__load_cotacoes()

  def reler_cotacoes(self, data_inicio, data_fim):
    self.data_inicio = data_inicio
    self.data_fim = data_fim
    self.cotacoes = self.__load_cotacoes()    

  def arredondar_casas_decimais(self, casas=2):
    self.patrimonio["liquido"] = self.patrimonio["liquido"].astype(float).round(casas)
    self.patrimonio["saldo"] = self.patrimonio["saldo"].astype(float).round(casas)
    self.patrimonio["capital"] = self.patrimonio["capital"].astype(float).round(casas)
    self.operacoes["preco"] = self.operacoes["preco"].astype(float).round(casas)
    self.posicoes["precoEntrada"] = self.posicoes["precoEntrada"].astype(float).round(casas)
    self.posicoes["precoSaida"] = self.posicoes["precoSaida"].astype(float).round(casas)
    self.posicoes["forcaRelativa"] = self.posicoes["forcaRelativa"].astype(float).round(casas)
    self.posicoes["stopLoss"] = self.posicoes["stopLoss"].astype(float).round(casas)

  # Funções de controle da evolução do patrimônio
  def atualizarPatrimonio(self, data, operacao, valor):
    liquidoAtual = self.patrimonio['liquido'].iloc[-1] if (self.patrimonio.liquido.size > 0) else 0
    saldoAtual = self.patrimonio['saldo'].iloc[-1] if (self.patrimonio.saldo.size > 0) else 0
    capitalAtual = self.patrimonio['capital'].iloc[-1] if (self.patrimonio.capital.size > 0) else 0
    if (operacao == 'DEPOSIT'):
      liquidoAtual = liquidoAtual + valor
      capitalAtual = capitalAtual + valor
      saldoAtual = saldoAtual + valor
    elif (operacao == 'DEC_LIQUIDO'):
      liquidoAtual = liquidoAtual - valor
    if (operacao == 'INC_LIQUIDO'):
      liquidoAtual = liquidoAtual + valor
    if (operacao == 'INC_SALDO'):
      saldoAtual = saldoAtual + valor
    if (operacao == 'DEC_SALDO'):
      saldoAtual = saldoAtual - valor
    elif (operacao == 'INC_CAPITAL'): 
      capitalAtual = saldoAtual + valor
    atualizacao = pd.Series({
        'data': data,
        'liquido': liquidoAtual,
        'saldo': saldoAtual,
        'capital': capitalAtual
    })
    self.patrimonio = pd.concat([self.patrimonio, atualizacao.to_frame().T], ignore_index=True)
 
  def temSaldoLiquido(self, valor):
    liquidoAtual = self.patrimonio['liquido'].iloc[-1] if (self.patrimonio.liquido.size > 0) else 0
    return True if (liquidoAtual >= valor) else False

  # Funções de controle das posições
  def abrirPosicao(self, dataEntrada, ativo, tipo, volume, precoEntrada, forcaRelativa, stopLoss=np.nan, stopGain=np.nan):
    if (type(dataEntrada) == str):
      dataEntrada = datetime.strptime(dataEntrada, '%Y-%m-%d')

    # Grava nova posição aberta
    novaPosicao = pd.Series({
        'ativo'        : ativo,
        'tipo'         : tipo,
        'volume'       : volume,
        'dataEntrada'  : dataEntrada,
        'precoEntrada' : precoEntrada,
        'forcaRelativa': forcaRelativa,
        'stopLoss'     : stopLoss,
        'stopGain'     : stopGain
    })
    self.posicoes = pd.concat([self.posicoes, novaPosicao.to_frame().T], ignore_index=True)
    custo_operacional = volume * precoEntrada * self.taxa_custo_operacional
    novaOperacao = pd.Series({
        'data'    : dataEntrada,
        'ativo'   : ativo,
        'tipo'    : tipo,
        'direcao' : 'IN',
        'volume'  : volume,
        'preco'   : precoEntrada,
        'custo'   : custo_operacional
    })
    self.operacoes = pd.concat([self.operacoes, novaOperacao.to_frame().T], ignore_index=True)
    if tipo == 'BUY':
      self.atualizarPatrimonio(dataEntrada, 'DEC_LIQUIDO', (volume * precoEntrada) + custo_operacional)
    #else:
      #self.atualizarPatrimonio(dataEntrada, 'INC_LIQUIDO', (volume * precoEntrada) - custo_operacional)
    self.atualizarPatrimonio(dataEntrada, 'DEC_SALDO', custo_operacional)


  def fecharPosicao(self, dataSaida, ativo, precoSaida):
    if (type(dataSaida) == str):
      dataSaida = datetime.strptime(dataSaida, '%Y-%m-%d')

    posicaoAberta = (self.posicoes['ativo'] == ativo) & self.posicoes['precoSaida'].isna()
    if (self.posicoes.loc[posicaoAberta, 'dataEntrada'].size == 1):
      # Atualiza a posição fechando-a
      self.posicoes.loc[posicaoAberta, 'dataSaida'] = dataSaida
      self.posicoes.loc[posicaoAberta, 'precoSaida'] = precoSaida
      precoEntrada = self.posicoes.loc[posicaoAberta, 'precoEntrada'].values[0]
      volume = self.posicoes.loc[posicaoAberta, 'volume'].values[0]
      tipo = self.posicoes.loc[posicaoAberta, 'tipo'].values[0]
      custo_operacional = volume * precoSaida * self.taxa_custo_operacional
      lucro = (precoSaida - precoEntrada) if tipo == "BUY" else (precoEntrada - precoSaida)
      resultado = lucro * volume
      self.posicoes.loc[posicaoAberta, 'resultado'] = round(resultado, 2)
      self.posicoes.loc[posicaoAberta, 'retorno'] = round(lucro / precoEntrada, 4)
      # Grava nova operação
      novaOperacao = pd.Series({
          'data'    : dataSaida,
          'ativo'   : ativo,
          'tipo'    : 'SELL' if tipo == 'BUY' else 'BUY',
          'direcao' : 'OUT',
          'volume'  : volume,
          'preco'   : precoSaida,
          'custo'   : custo_operacional
      })
      self.operacoes = pd.concat([self.operacoes, novaOperacao.to_frame().T], ignore_index=True)
      # Atualiza patrimônio
      if tipo == 'BUY':
        self.atualizarPatrimonio(dataSaida, 'INC_LIQUIDO', (volume * precoSaida) - custo_operacional)
      #else:
        #self.atualizarPatrimonio(dataSaida, 'DEC_LIQUIDO', (volume * precoSaida) + custo_operacional)
      self.atualizarPatrimonio(dataSaida, 'INC_SALDO', resultado)
      self.atualizarPatrimonio(dataSaida, 'DEC_SALDO', custo_operacional)
    return resultado

  def temPosicaoAberta(self, ativo):
    return True if self.posicoes.loc[(self.posicoes['ativo'] == ativo) & self.posicoes['precoSaida'].isna(), 'tipo'].size == 1 else False

  def getStopLossPosicaoAberta(self, ativo):
    return self.posicoes.loc[(self.posicoes['ativo'] == ativo) & self.posicoes['precoSaida'].isna(), 'stopLoss'].iloc[0]

  def getStopGainPosicaoAberta(self, ativo):
    return self.posicoes.loc[(self.posicoes['ativo'] == ativo) & self.posicoes['precoSaida'].isna(), 'stopGain'].iloc[0]

  def subirStopLossPosicaoAberta(self, ativo, novoStopLoss):
    posicaoAberta = (self.posicoes['ativo'] == ativo) & self.posicoes['precoSaida'].isna()
    if (self.posicoes.loc[posicaoAberta, 'dataEntrada'].size == 1):
      # Atualiza stoploss da posição
      self.posicoes.loc[posicaoAberta, 'stopLoss'] = novoStopLoss

  def getQuantidadePosicoesAbertas(self):
    return self.posicoes.loc[self.posicoes['precoSaida'].isna(), 'ativo'].count()

  def getTipoPosicaoAberta(self, ativo):
    posicoesAbertas = self.posicoes.loc[(self.posicoes['ativo'] == ativo) & self.posicoes['precoSaida'].isna(), 'tipo']
    return posicoesAbertas.values[0] if posicoesAbertas.size == 1 else np.nan

  def getResultadoPosicaoAberta(self, ativo, precoAtual):
    posicaoAberta = (self.posicoes['ativo'] == ativo) & self.posicoes['precoSaida'].isna()
    if (self.posicoes.loc[posicaoAberta, 'dataEntrada'].size == 1):
      precoEntrada = self.posicoes.loc[posicaoAberta, 'precoEntrada'].values[0]
      volume = self.posicoes.loc[posicaoAberta, 'volume'].values[0]
      tipo = self.posicoes.loc[posicaoAberta, 'tipo'].values[0]
      if (tipo == 'BUY'):
        resultado = (precoAtual - precoEntrada) * volume
      else:
        resultado = (precoEntrada - precoAtual) * volume
    return resultado

  def getResultadoPosicoesAbertas(self, data):
    posicoesAbertas = self.posicoes.loc[self.posicoes['precoSaida'].isna(), ['ativo', 'volume', 'precoEntrada', 'tipo']].copy()

    # Obter os preços de fechamento na data fornecida
    precos_fechamento = self.pregoes.loc[data, (posicoesAbertas['ativo'], 'Close')]

    # Associar os preços de fechamento aos ativos da posição aberta
    posicoesAbertas['Close'] = posicoesAbertas['ativo'].map(precos_fechamento)

    #posicoesAbertas = posicoesAbertas.assign(Close = self.pregoes.loc[data, (posicoesAbertas['ativo'], 'Close')].values)
    # Calcular o resultado com base no tipo de posição (BUY ou SELL)
    posicoesAbertas['resultado'] = posicoesAbertas.apply(
        lambda row: (row['Close'] - row['precoEntrada']) * row['volume']
        if row['tipo'] == 'BUY'
        else (row['precoEntrada'] - row['Close']) * row['volume'],
        axis=1
    )
    return posicoesAbertas['resultado'].sum()

  def getCapitalPosicoesAbertas(self, data):
    posicoesAbertas = self.posicoes.loc[self.posicoes['precoSaida'].isna(), ['ativo', 'volume', 'precoEntrada']].copy().reset_index()
    posicoesAbertas = posicoesAbertas.assign(Close = self.pregoes.loc[data, (posicoesAbertas['ativo'], 'Close')].values)
    posicoesAbertas['capital'] = posicoesAbertas['Close'] * posicoesAbertas['volume']
    return posicoesAbertas['capital'].sum()

  def getVolumeOperacao(self, preco):
    capitalInicial = self.patrimonio['capital'].iloc[0]
    saldoAtual = self.patrimonio['saldo'].iloc[-1] if (self.patrimonio.saldo.size > 0) else 0
    if self.reinvestir_lucros or (saldoAtual < capitalInicial):
      valorOperacao = saldoAtual / self.diversificacao_maxima
    else:
      valorOperacao = capitalInicial / self.diversificacao_maxima
    result = 100 * int(valorOperacao / 100 / preco) if (preco > 0) else 0
    return result

  def fmtMonetario(self, valor):
    return "R$ {:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

  def get_rentabilidade_media(self, frequencia='A'):
    # Certificando que a coluna 'data' é do tipo datetime
    self.patrimonio['data'] = pd.to_datetime(self.patrimonio['data'])

    # Rentabilidade média conforme a frequência informada
    capital_agrupado = self.patrimonio.set_index('data', inplace=False)['capital'].resample(frequencia).last()
    capital_inicial_index = pd.Index([self.patrimonio.iloc[0]['data']]).infer_objects()
    capital_inicial = pd.Series([self.patrimonio.iloc[0]['capital']], index=capital_inicial_index)
    capital_agrupado = pd.concat([capital_inicial, capital_agrupado])
    rentabilidade_media = pd.DataFrame(capital_agrupado, columns=['capital'])
    rentabilidade_media['variacao'] = rentabilidade_media['capital'].pct_change()
    rentabilidade_media.dropna(inplace=True)
    rentabilidade_media['retorno'] = rentabilidade_media['variacao'].map(lambda x: "{:.2%}".format(x))
    return rentabilidade_media

  def getMetricas(self, frequencia_rentabilidade='A', taxa_livre_risco_aa=0.10):
    capitalInicial = self.patrimonio['capital'].iloc[0]
    # Lucro
    lucroLiquidoFin = self.posicoes.resultado.sum()
    lucroLiquidoPerc = self.posicoes.retorno.sum()
    rentabilidade = (lucroLiquidoFin / capitalInicial) * 100
    # Drawdown
    picos = self.patrimonio['saldo'].cummax()
    drawdownFin = (self.patrimonio['saldo'] - picos)
    drawdownPercent = drawdownFin / picos
    drawdownMaxFin = -drawdownFin.min()
    drawdownMaxPercent = drawdownPercent.min() * -100
    # Fator de recuperação
    try:
      if (self.reinvestir_lucros):
        fatorRecuperacao = rentabilidade / drawdownMaxPercent
      else:
        fatorRecuperacao = lucroLiquidoFin / drawdownMaxFin
    except ZeroDivisionError:
      fatorRecuperacao = 0
    totalPosicoes = self.posicoes.dataEntrada.count()
    totalOperacoes = self.operacoes.data.count()
    lucroFinPorOperacao = lucroLiquidoFin / totalPosicoes
    lucroPercPorOperacao = lucroLiquidoPerc / totalPosicoes
    posicoesVencedoras = self.posicoes.loc[self.posicoes['resultado'] > 0, 'dataEntrada'].count()
    taxaAcerto = posicoesVencedoras / totalPosicoes
    lucroMedioFin = self.posicoes.loc[self.posicoes['resultado'] > 0, 'resultado'].mean()
    perdaMediaFin = abs(self.posicoes.loc[self.posicoes['resultado'] <= 0, 'resultado'].mean())
    lucroMedioPerc = self.posicoes.loc[self.posicoes['retorno'] > 0, 'retorno'].mean()
    perdaMediaPerc = abs(self.posicoes.loc[self.posicoes['retorno'] <= 0, 'retorno'].mean())
    payoff = lucroMedioPerc / perdaMediaPerc
    somaLucrosPerc = self.posicoes.loc[self.posicoes['retorno'] > 0, 'retorno'].sum()
    somaPrejuizosPerc = abs(self.posicoes.loc[self.posicoes['retorno'] <= 0, 'retorno'].sum())
    profitFactor = somaLucrosPerc / somaPrejuizosPerc
    expectativaMatematica = (taxaAcerto * lucroMedioFin) - ((1-taxaAcerto) * perdaMediaFin)
    expectativaMatematicaNormalizada = (payoff * taxaAcerto) - (1-taxaAcerto)
    ultimoPregao = self.pregoes.index[-1]
    resultadoPosicoesAbertas = self.getResultadoPosicoesAbertas(ultimoPregao)
    capitalPosicoesAbertas = self.getCapitalPosicoesAbertas(ultimoPregao)
    capitalAtual = self.patrimonio['capital'].iloc[-1]
    liquidoAtual = self.patrimonio['liquido'].iloc[-1]
    rentabilidade_media = self.get_rentabilidade_media(frequencia_rentabilidade)

    # Cálculo do Índice de Sharpe para dados diários
    retornos_diarios = self.posicoes.groupby("dataEntrada").agg(total_retorno=("retorno", "sum")).reset_index()
    sharpe = calcular_sharpe(retornos_diarios, 'total_retorno', taxa_livre_risco_aa, freq='diária')

    # Apresentação dos resultados
    print('Ativos operados     :', self.indice_b3)
    print('Data início         :', self.data_inicio)
    print('Data fim            :', self.data_fim)
    print('Capital inicial     :', self.fmtMonetario(capitalInicial))
    print('Diversificação max. :', self.diversificacao_maxima)
    print('Reinvestir lucros   :', 'Sim' if self.reinvestir_lucros else 'Não')
    print('Taxa custo bolsa    : %.3f %%' %(self.taxa_custo_operacional*100))
    print('--------------------')
    print('Lucro líquido       :', self.fmtMonetario(lucroLiquidoFin))
    print('Rentabilidade       : %.2f %%' %rentabilidade)
    print('Saldo atual         :', self.fmtMonetario(capitalInicial + lucroLiquidoFin))
    print('--------------------')
    print('Drawdown máximo pct.: %.2f %%' %drawdownMaxPercent)
    print('Fator de recuperação: %.2f' %fatorRecuperacao)
    print('--------------------')
    print('Taxa de acerto      : %.2f %%' %(taxaAcerto*100))
    print('Fator de Lucro      : %.2f' %profitFactor)
    print('Payoff              : %.2f' %payoff)
    print(f"Índice de Sharpe    : {sharpe:.2f}")
    print('--------------------')
    print('Total de operações  : %d' %totalOperacoes)
    print('Total de posições   : %d' %totalPosicoes)
    print('Drawdown máximo fin.:', self.fmtMonetario(drawdownMaxFin))
    print('--------------------')
    print('Lucro médio         :', self.fmtMonetario(lucroMedioFin), '(%.2f %%)' %(lucroMedioPerc * 100))
    print('Perda média         :', self.fmtMonetario(perdaMediaFin), '(%.2f %%)' %(perdaMediaPerc * 100))
    print('Lucro por operação  :', self.fmtMonetario(lucroFinPorOperacao), '(%.2f %%)' %(lucroPercPorOperacao * 100))
    print('--------------------')
    print('Expect. mat.        :', self.fmtMonetario(expectativaMatematica))
    print('Expect. mat. norm.  : %.2f' %expectativaMatematicaNormalizada)
    print('--------------------')
    print('Result. pos. abertas:', self.fmtMonetario(resultadoPosicoesAbertas))
    print('Capital atual       :', self.fmtMonetario(capitalAtual))
    print('--------------------')
    print('Conta corrente:     :', self.fmtMonetario(liquidoAtual))
    print('Capital pos. abertas:', self.fmtMonetario(capitalPosicoesAbertas))
    print(f"CAGR                : {rentabilidade_media['variacao'].mean() * 100:.2f}% {frequencia_rentabilidade}")
    #"Rentabilidade média anual: {:.2f}%".format(rentabilidade_media['variacao'].mean() * 100)



  def plotar_curva_capital(self, plot_saldo=True, plot_capital=True, plot_liquido=True):
    datas = self.patrimonio['data']
    plt.figure(figsize=(20,10))
    if (plot_saldo):
      plt.plot(datas, self.patrimonio['saldo'].values, label='Saldo')
    if (plot_capital):
      plt.plot(datas, self.patrimonio['capital'].values, label='Capital')
    if (plot_liquido):
      plt.plot(datas, self.patrimonio['liquido'].values, label='Líquido')
    plt.xlabel("Data")
    plt.ylabel("Lucro")
    plt.legend()
    plt.title('Evolução do Patrimônio')  # Título do gráfico
    plt.grid(True)  # Adicionar grade
    plt.show()

def calcular_sharpe(df, coluna_retorno, taxa_livre_risco_anual, freq='diária'):
    """
    Calcula o Índice de Sharpe para um conjunto de retornos.
    
    Parâmetros:
    df (pd.DataFrame): DataFrame contendo os retornos dos trades.
    coluna_retorno (str): Nome da coluna no DataFrame com os retornos percentuais (exemplo: 0.02 para 2%).
    taxa_livre_risco_anual (float): Taxa livre de risco anual (exemplo: 0.1 para 10%).
    freq (str): Frequência dos dados ('diária', 'semanal' ou 'mensal').

    Retorna:
    float: Índice de Sharpe calculado.
    """

    # Definir o fator de ajuste para a taxa livre de risco e volatilidade
    fatores = {'diária': 252, 'semanal': 52, 'mensal': 12}
    if freq not in fatores:
        raise ValueError("A frequência deve ser 'diária', 'semanal' ou 'mensal'.")

    fator_ajuste = fatores[freq]

    # Calcular retorno médio da estratégia (ajustado para a periodicidade)
    retorno_medio = df[coluna_retorno].mean()

    # Ajustar a taxa livre de risco para a periodicidade correspondente
    taxa_livre_risco = taxa_livre_risco_anual / fator_ajuste

    # Calcular volatilidade dos retornos (desvio padrão)
    volatilidade = df[coluna_retorno].std()

    # Calcular Índice de Sharpe
    sharpe_ratio = (retorno_medio - taxa_livre_risco) / volatilidade

    return sharpe_ratio



# ============================================================================
# PARTE 2: NOVOS MÉTODOS PARA ADICIONAR NA CLASSE CARTEIRA
# ============================================================================

def ativar_filtro_mm5(self, criterio='crescente'):
    """
    Ativa o filtro de média móvel de 5 dias na curva de capital.
    
    Parameters:
    -----------
    criterio : str
        'crescente': opera apenas se MM5(hoje) > MM5(ontem)
        'acima_capital': opera apenas se MM5(hoje) > capital(ontem)
        'tendencia': opera se a tendência da MM5 é positiva
        'sempre': sempre opera (útil para comparação)
    
    Usage:
    ------
    bt_carteira.ativar_filtro_mm5('crescente')
    """
    self.filtro_mm5_ativo = True
    self.mm5_criterio = criterio
    self.mm5_historico_diario = []
    self.mm5_dia_atual = None
    self.mm5_capital_inicio_dia = None
    self.mm5_ultimos_5_dias = deque(maxlen=5)
    self.mm5_valor = None
    self.mm5_valor_anterior = None
    self.mm5_pode_operar_hoje = True
    self.mm5_operacoes_dia = 0
    
    print(f"✓ Filtro MM5 ATIVADO | Critério: '{criterio}'")
    print(f"  - Opera apenas quando a MM5 de capital atender ao critério")
    print(f"  - Primeiros 5 dias sempre operam (histórico insuficiente)")


def desativar_filtro_mm5(self):
    """Desativa o filtro de média móvel"""
    self.filtro_mm5_ativo = False
    print("✓ Filtro MM5 desativado - operando em todos os dias")


def _iniciar_novo_dia_mm5(self, pregao):
    """
    Processa a mudança de dia e calcula se pode operar hoje.
    Chamado automaticamente por pode_operar_hoje_mm5().
    """
    if not self.filtro_mm5_ativo:
        return
    
    # Se mudou de dia, finaliza o anterior
    if self.mm5_dia_atual is not None and self.mm5_dia_atual != pregao:
        self._finalizar_dia_mm5()
    
    # Inicia processamento do novo dia
    if self.mm5_dia_atual != pregao:
        self.mm5_dia_atual = pregao
        self.mm5_operacoes_dia = 0
        
        # Capital no início deste dia
        self.mm5_capital_inicio_dia = self.patrimonio['capital'].iloc[-1]
        
        # Adiciona à fila dos últimos 5 dias
        self.mm5_ultimos_5_dias.append(self.mm5_capital_inicio_dia)
        
        # Calcula a nova MM5
        self.mm5_valor_anterior = self.mm5_valor
        self.mm5_valor = np.mean(list(self.mm5_ultimos_5_dias))
        
        # Avalia se pode operar hoje
        self.mm5_pode_operar_hoje = self._avaliar_criterio_mm5()


def _finalizar_dia_mm5(self):
    """
    Registra estatísticas do dia que acabou.
    Chamado automaticamente quando muda de dia.
    """
    if not self.filtro_mm5_ativo or self.mm5_dia_atual is None:
        return
    
    capital_fim_dia = self.patrimonio['capital'].iloc[-1]
    resultado_dia = capital_fim_dia - self.mm5_capital_inicio_dia
    
    self.mm5_historico_diario.append({
        'data': self.mm5_dia_atual,
        'capital_inicio': self.mm5_capital_inicio_dia,
        'capital_fim': capital_fim_dia,
        'resultado': resultado_dia,
        'mm5': self.mm5_valor,
        'mm5_anterior': self.mm5_valor_anterior,
        'operou': self.mm5_pode_operar_hoje,
        'n_operacoes': self.mm5_operacoes_dia
    })


def _avaliar_criterio_mm5(self):
    """
    Decide se pode operar hoje baseado no critério configurado.
    
    Returns:
    --------
    bool : True se pode operar, False se deve pular o dia
    """
    # Primeiros 5 dias sempre operam
    if len(self.mm5_ultimos_5_dias) < 5:
        return True
    
    if self.mm5_valor_anterior is None:
        return True
    
    # Aplica o critério escolhido
    if self.mm5_criterio == 'crescente':
        # Opera se MM5 hoje > MM5 ontem
        return self.mm5_valor > self.mm5_valor_anterior
    
    elif self.mm5_criterio == 'acima_capital':
        # Opera se MM5 hoje > capital de ontem
        if len(self.mm5_ultimos_5_dias) >= 2:
            capital_ontem = list(self.mm5_ultimos_5_dias)[-2]
            return self.mm5_valor > capital_ontem
        return True
    
    elif self.mm5_criterio == 'tendencia':
        # Opera se a tendência (inclinação) é positiva
        diferenca = self.mm5_valor - self.mm5_valor_anterior
        return diferenca > 0
    
    elif self.mm5_criterio == 'sempre':
        # Sempre opera (útil para comparação)
        return True
    
    # Default: opera
    return True


def pode_operar_hoje_mm5(self, pregao):
    """
    MÉTODO PRINCIPAL: Verifica se pode operar no dia.
    
    Deve ser chamado no início de cada iteração do loop de pregão,
    ANTES do loop de ativos.
    
    Parameters:
    -----------
    pregao : datetime
        Data do pregão atual
    
    Returns:
    --------
    bool : True se pode operar hoje, False se deve pular o dia inteiro
    
    Usage:
    ------
    for pregao in bt_carteira.pregoes.index:
        if not bt_carteira.pode_operar_hoje_mm5(pregao):
            bt_carteira.atualizarPatrimonio(pregao, 'INC_CAPITAL', 
                                           bt_carteira.getResultadoPosicoesAbertas(pregao))
            continue
        
        for ativo in bt_carteira.ativos.itertuples():
            # ... seu código normal ...
    """
    if not self.filtro_mm5_ativo:
        return True
    
    # Processa o dia (calcula MM5 e decide se opera)
    self._iniciar_novo_dia_mm5(pregao)
    
    return self.mm5_pode_operar_hoje


def registrar_operacao_mm5(self):
    """
    Registra que uma operação foi realizada.
    
    Chame este método após:
    - bt_carteira.abrirPosicao(...)
    - bt_carteira.fecharPosicao(...)
    
    Usage:
    ------
    bt_carteira.abrirPosicao(pregao, ativo, 'BUY', volume, preco, obs, sl, sg)
    bt_carteira.registrar_operacao_mm5()
    """
    if self.filtro_mm5_ativo:
        self.mm5_operacoes_dia += 1


def finalizar_backtest_mm5(self):
    """
    Finaliza o registro do último dia.
    Chame ao final do backtest, antes de imprimir relatórios.
    
    Usage:
    ------
    # Após o loop de backtest
    bt_carteira.finalizar_backtest_mm5()
    bt_carteira.getMetricas()
    bt_carteira.imprimir_relatorio_mm5()
    """
    if self.filtro_mm5_ativo and self.mm5_dia_atual is not None:
        self._finalizar_dia_mm5()


def get_relatorio_mm5(self):
    """
    Retorna DataFrame com histórico diário completo do filtro MM5.
    
    Returns:
    --------
    DataFrame com colunas:
        - data: data do pregão
        - capital_inicio: capital no início do dia
        - capital_fim: capital no fim do dia
        - resultado: resultado do dia
        - mm5: valor da média móvel de 5 dias
        - mm5_anterior: valor da MM5 do dia anterior
        - operou: True se operou, False se ficou parado
        - n_operacoes: quantidade de operações no dia
        - retorno_dia_pct: retorno percentual do dia
        - peak: pico de capital até o momento
        - drawdown_pct: drawdown percentual
    
    Usage:
    ------
    df = bt_carteira.get_relatorio_mm5()
    print(df.tail(10))
    df.to_csv('relatorio_mm5.csv', index=False)
    """
    if not self.mm5_historico_diario:
        print("⚠️  Nenhum dado de MM5 disponível")
        return None
    
    df = pd.DataFrame(self.mm5_historico_diario)
    
    # Métricas adicionais
    df['retorno_dia_pct'] = (df['capital_fim'] / df['capital_inicio'] - 1) * 100
    df['peak'] = df['capital_fim'].cummax()
    df['drawdown_pct'] = (df['capital_fim'] - df['peak']) / df['peak'] * 100
    
    return df


def get_estatisticas_mm5(self):
    """
    Retorna dicionário com estatísticas comparativas do filtro MM5.
    
    Returns:
    --------
    dict com estatísticas de:
        - configuração (critério, dias totais, dias operados)
        - performance (capital, retorno, drawdown)
        - comparativo dias operados vs parados
    
    Usage:
    ------
    stats = bt_carteira.get_estatisticas_mm5()
    print(f"Retorno: {stats['retorno_pct']:.2f}%")
    print(f"Operou {stats['pct_dias_operados']:.1f}% dos dias")
    """
    if not self.mm5_historico_diario:
        print("⚠️  Nenhum dado de MM5 disponível")
        return None
    
    df = pd.DataFrame(self.mm5_historico_diario)
    
    dias_total = len(df)
    dias_operados = df['operou'].sum()
    dias_parados = dias_total - dias_operados
    
    capital_inicial = df['capital_inicio'].iloc[0]
    capital_final = df['capital_fim'].iloc[-1]
    resultado = capital_final - capital_inicial
    retorno_pct = (capital_final / capital_inicial - 1) * 100
    
    # Drawdown máximo
    df['peak'] = df['capital_fim'].cummax()
    df['drawdown_pct'] = (df['capital_fim'] - df['peak']) / df['peak'] * 100
    max_drawdown = df['drawdown_pct'].min()
    
    # Separar dias operados vs parados
    df_operados = df[df['operou'] == True]
    df_parados = df[df['operou'] == False]
    
    resultado_dias_operados = df_operados['resultado'].sum() if len(df_operados) > 0 else 0
    resultado_dias_parados = df_parados['resultado'].sum() if len(df_parados) > 0 else 0
    
    # Retorno médio por dia
    retorno_medio_operado = df_operados['resultado'].mean() if len(df_operados) > 0 else 0
    retorno_medio_parado = df_parados['resultado'].mean() if len(df_parados) > 0 else 0
    
    # Volatilidade
    volatilidade_operado = df_operados['resultado'].std() if len(df_operados) > 1 else 0
    volatilidade_parado = df_parados['resultado'].std() if len(df_parados) > 1 else 0
    
    return {
        'configuracao': {
            'criterio': self.mm5_criterio,
            'filtro_ativo': self.filtro_mm5_ativo
        },
        'dias': {
            'total': dias_total,
            'operados': int(dias_operados),
            'parados': int(dias_parados),
            'pct_operados': (dias_operados / dias_total) * 100 if dias_total > 0 else 0
        },
        'performance': {
            'capital_inicial': capital_inicial,
            'capital_final': capital_final,
            'resultado': resultado,
            'retorno_pct': retorno_pct,
            'max_drawdown_pct': max_drawdown
        },
        'dias_operados': {
            'resultado_total': resultado_dias_operados,
            'resultado_medio': retorno_medio_operado,
            'volatilidade': volatilidade_operado,
            'total_operacoes': int(df_operados['n_operacoes'].sum()) if len(df_operados) > 0 else 0
        },
        'dias_parados': {
            'resultado_total': resultado_dias_parados,
            'resultado_medio': retorno_medio_parado,
            'volatilidade': volatilidade_parado
        }
    }


def imprimir_relatorio_mm5(self):
    """
    Imprime relatório formatado e detalhado do filtro MM5.
    
    Usage:
    ------
    bt_carteira.finalizar_backtest_mm5()
    bt_carteira.imprimir_relatorio_mm5()
    """
    stats = self.get_estatisticas_mm5()
    
    if stats is None:
        return
    
    print("\n" + "="*75)
    print("           RELATÓRIO DO FILTRO DE MÉDIA MÓVEL 5 DIAS")
    print("="*75)
    
    print(f"\n📊 CONFIGURAÇÃO")
    print(f"   Critério........: {stats['configuracao']['criterio']}")
    print(f"   Status..........: {'ATIVO' if stats['configuracao']['filtro_ativo'] else 'INATIVO'}")
    
    print(f"\n📅 DIAS DE OPERAÇÃO")
    print(f"   Dias totais.....: {stats['dias']['total']}")
    print(f"   Dias operados...: {stats['dias']['operados']} ({stats['dias']['pct_operados']:.1f}%)")
    print(f"   Dias parados....: {stats['dias']['parados']} ({100-stats['dias']['pct_operados']:.1f}%)")
    
    print(f"\n💰 PERFORMANCE GERAL")
    print(f"   Capital inicial.: {self.fmtMonetario(stats['performance']['capital_inicial'])}")
    print(f"   Capital final...: {self.fmtMonetario(stats['performance']['capital_final'])}")
    print(f"   Resultado.......: {self.fmtMonetario(stats['performance']['resultado'])}")
    print(f"   Retorno.........: {stats['performance']['retorno_pct']:.2f}%")
    print(f"   Max Drawdown....: {stats['performance']['max_drawdown_pct']:.2f}%")
    
    print(f"\n📈 DIAS OPERADOS")
    print(f"   Resultado acum..: {self.fmtMonetario(stats['dias_operados']['resultado_total'])}")
    print(f"   Resultado médio.: {self.fmtMonetario(stats['dias_operados']['resultado_medio'])}")
    print(f"   Volatilidade....: {self.fmtMonetario(stats['dias_operados']['volatilidade'])}")
    print(f"   Total operações.: {stats['dias_operados']['total_operacoes']}")
    
    print(f"\n📉 DIAS PARADOS")
    print(f"   Resultado acum..: {self.fmtMonetario(stats['dias_parados']['resultado_total'])}")
    print(f"   Resultado médio.: {self.fmtMonetario(stats['dias_parados']['resultado_medio'])}")
    print(f"   Volatilidade....: {self.fmtMonetario(stats['dias_parados']['volatilidade'])}")
    
    # Análise adicional
    if stats['dias']['parados'] > 0:
        economia_volatilidade = stats['dias_operados']['volatilidade'] - stats['dias_parados']['volatilidade']
        print(f"\n💡 INSIGHTS")
        if stats['dias_parados']['resultado_medio'] < 0:
            print(f"   ✓ Filtro evitou {stats['dias']['parados']} dias com resultado médio negativo")
            print(f"   ✓ Perda média evitada: {self.fmtMonetario(abs(stats['dias_parados']['resultado_medio']))}/dia")
        if economia_volatilidade > 0:
            print(f"   ✓ Redução de volatilidade: {self.fmtMonetario(economia_volatilidade)}")
    
    print("="*75 + "\n")


def comparar_com_sem_filtro(self, stats_sem_filtro):
    """
    Compara resultados com e sem filtro MM5.
    
    Parameters:
    -----------
    stats_sem_filtro : dict
        Dicionário com estatísticas do backtest sem filtro
        (use get_estatisticas_mm5() ou extraia do getMetricas())
    
    Usage:
    ------
    # Após rodar backtest SEM filtro
    stats_sem = {
        'capital_final': bt_carteira_sem.patrimonio['capital'].iloc[-1],
        'retorno_pct': ...,
        'max_drawdown_pct': ...,
    }
    
    # Após rodar backtest COM filtro
    bt_carteira_com.comparar_com_sem_filtro(stats_sem)
    """
    stats_com = self.get_estatisticas_mm5()
    
    if stats_com is None:
        print("⚠️  Execute o backtest com filtro MM5 primeiro")
        return
    
    print("\n" + "="*75)
    print("              COMPARAÇÃO: SEM FILTRO vs COM FILTRO MM5")
    print("="*75)
    
    print(f"\n                     SEM FILTRO       COM FILTRO       DIFERENÇA")
    print("-"*75)
    
    # Capital final
    cap_sem = stats_sem_filtro.get('capital_final', 0)
    cap_com = stats_com['performance']['capital_final']
    dif_cap = cap_com - cap_sem
    print(f"Capital Final   {cap_sem:>14,.2f}  {cap_com:>14,.2f}  {dif_cap:>+14,.2f}")
    
    # Retorno
    ret_sem = stats_sem_filtro.get('retorno_pct', 0)
    ret_com = stats_com['performance']['retorno_pct']
    dif_ret = ret_com - ret_sem
    print(f"Retorno (%)     {ret_sem:>14.2f}  {ret_com:>14.2f}  {dif_ret:>+14.2f}")
    
    # Drawdown
    dd_sem = stats_sem_filtro.get('max_drawdown_pct', 0)
    dd_com = stats_com['performance']['max_drawdown_pct']
    dif_dd = dd_com - dd_sem
    melhoria_dd = "MELHOR" if dif_dd > 0 else "PIOR"
    print(f"Max DD (%)      {dd_sem:>14.2f}  {dd_com:>14.2f}  {dif_dd:>+14.2f} {melhoria_dd}")
    
    print("\n" + "="*75 + "\n")




