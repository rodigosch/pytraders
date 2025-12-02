import yfinance as yf
import pandas as pd
import numpy as np
from time import sleep
from selenium.webdriver.common.by import By
import os
from selenium import webdriver
import chromedriver_autoinstaller
from .trading_book import TradingBook

class Carteira:
    def __init__(self, indice_b3, data_inicio, data_fim):
        chromedriver_autoinstaller.install()
        self.indice_b3 = indice_b3
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.filtrar_operacao_curva_capital = False
        self.book_execucao = None
        self.book_referencia = None


    def setup_backtest(self, capital_inicial, diversificacao_maxima, reinvestir_lucros, taxa_custo_operacional, pregoes, filtrar_operacao_curva_capital=False):
        self.filtrar_operacao_curva_capital = filtrar_operacao_curva_capital
        self.book_execucao = TradingBook(self.indice_b3, self.data_inicio, self.data_fim, capital_inicial, diversificacao_maxima, reinvestir_lucros, taxa_custo_operacional, pregoes, filtrar_operacao_curva_capital)
        if (self.filtrar_operacao_curva_capital):
            self.book_referencia = TradingBook(self.indice_b3, self.data_inicio, self.data_fim, capital_inicial, diversificacao_maxima, reinvestir_lucros, taxa_custo_operacional, pregoes, filtrar_operacao_curva_capital)


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

    def atualizarPatrimonio(self, data, operacao, valor):
        self.book_execucao.atualizarPatrimonio(data, operacao, valor)
        if (self.filtrar_operacao_curva_capital):
            self.book_referencia.atualizarPatrimonio(data, operacao, valor)

    def temPosicaoAberta(self, ativo):
        return self.book_execucao.temPosicaoAberta(ativo)
    
    def getStopLossPosicaoAberta(self, ativo):
        return self.book_execucao.getStopLossPosicaoAberta(ativo)
    
    def getStopGainPosicaoAberta(self, ativo):
        return self.book_execucao.getStopGainPosicaoAberta(ativo)
    
    def getTipoPosicaoAberta(self, ativo):
        return self.book_execucao.getTipoPosicaoAberta(ativo)
    
    def fecharPosicao(self, dataSaida, ativo, precoSaida):
        self.book_execucao.fecharPosicao(dataSaida, ativo, precoSaida)
        if (self.filtrar_operacao_curva_capital):
            self.book_referencia.fecharPosicao(dataSaida, ativo, precoSaida)

    def getVolumeOperacao(self, preco):
        return self.book_execucao.getVolumeOperacao(preco)

    def temSaldoLiquido(self, valor):
        return self.book_execucao.temSaldoLiquido(valor)
    
    def getQuantidadePosicoesAbertas(self):
        return self.book_execucao.getQuantidadePosicoesAbertas()

    def abrirPosicao(self, dataEntrada, ativo, tipo, volume, precoEntrada, forcaRelativa, stopLoss=np.nan, stopGain=np.nan):
        if (self.filtrar_operacao_curva_capital):
            self.book_referencia.abrirPosicao(dataEntrada, ativo, tipo, volume, precoEntrada, forcaRelativa, stopLoss, stopGain)
        if ((self.filtrar_operacao_curva_capital and self.book_referencia.curva_capital_acima_media_movel()) or not self.filtrar_operacao_curva_capital):
            self.book_execucao.abrirPosicao(dataEntrada, ativo, tipo, volume, precoEntrada, forcaRelativa, stopLoss, stopGain)

    def getResultadoPosicoesAbertas(self, data):
        return self.book_execucao.getResultadoPosicoesAbertas(data)
    
    def arredondar_casas_decimais(self, casas=2):
        self.book_execucao.arredondar_casas_decimais(casas)
        if (self.filtrar_operacao_curva_capital):
            self.book_referencia.arredondar_casas_decimais(casas)