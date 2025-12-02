from datetime import datetime
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

class TradingBook:
    def __init__(self, indice_b3, data_inicio, data_fim, capital_inicial, diversificacao_maxima, reinvestir_lucros, taxa_custo_operacional, pregoes, filtrar_operacao_curva_capital=False, sma_curva_capital=5):
        self.indice_b3 = indice_b3
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.diversificacao_maxima = diversificacao_maxima
        self.reinvestir_lucros = reinvestir_lucros
        self.taxa_custo_operacional = taxa_custo_operacional
        self.pregoes = pregoes
        self.filtrar_operacao_curva_capital = filtrar_operacao_curva_capital
        self.sma_curva_capital = sma_curva_capital

        # Dataframe da evolução do patrimônio
        # liquido: valor em conta corrente disponível para compras
        # saldo: demonstra evolução do capital considerando somente o saldo de posições fechadas
        # capital: demonstra evolução do capital considerando também a cotação das posições abertas
        self.patrimonio = pd.DataFrame(columns=['data', 'liquido', 'saldo', 'capital'])
        # Dataframe das posições
        self.posicoes = pd.DataFrame(columns=('ativo', 'tipo', 'volume', 'dataEntrada', 'precoEntrada', 'dataSaida', 'precoSaida', 'resultado', 'retorno', 'forcaRelativa', 'stopLoss', 'stopGain'))
        # Dataframe das operações
        self.operacoes = pd.DataFrame(columns=['data', 'ativo', 'tipo', 'direcao', 'volume', 'preco', 'custo'])
        # Dataframe de Resumo Diário (Curva de Capital consolidada)
        # Index será a Data (DatetimeIndex) para facilitar o resampling e upsert
        self.capital_diario = pd.DataFrame(columns=['saldo', 'capital', 'media_movel_5d'])
        self.capital_diario.index.name = 'data'
        self.atualizarPatrimonio(pd.to_datetime(self.data_inicio), 'DEPOSIT', capital_inicial)

    # Nova função privada para gerenciar a lógica de média móvel e dia único
    def __atualizar_capital_diario(self, data, saldo, capital):
        # Normaliza para garantir que horas não dupliquem linhas (apenas a data importa para curva diária)
        data_normalizada = pd.to_datetime(data).normalize()

        # Atualiza ou Cria a linha para este dia (Upsert)
        # Usamos .loc para garantir que se houver 10 trades no dia, ficaremos com o valor do último (fechamento do dia)
        self.capital_diario.loc[data_normalizada, 'saldo'] = float(saldo)
        self.capital_diario.loc[data_normalizada, 'capital'] = float(capital)

        # Lógica da Média Móvel Simples de 5 períodos (SMA 5)
        # Pegamos as últimas 5 linhas da coluna saldo.
        # Como acabamos de atualizar a linha atual (data_normalizada), ela já está incluída no tail(5)
        window = self.capital_diario['saldo'].tail(self.sma_curva_capital)

        if len(window) == 5:
            media_movel = window.mean()
        else:
            # Opcional: Se quiser média expandida enquanto não tem 5 dias, use window.mean()
            # Se quiser NaN estrito até ter 5 dias, use np.nan
            media_movel = np.nan

        self.capital_diario.loc[data_normalizada, 'media_movel_5d'] = media_movel

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

        # Alimenta o dataframe diário consolidado após o registro do evento
        self.__atualizar_capital_diario(data, saldoAtual, capitalAtual)

    def curva_capital_acima_media_movel(self):
        if self.capital_diario.empty:
            return True
        else:
            ultima_linha = self.capital_diario.iloc[-1]
            capital_atual = ultima_linha['capital']
            media_movel_5d = ultima_linha['media_movel_5d']
            if pd.isna(media_movel_5d):
                return True
            return capital_atual >= media_movel_5d

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
            
        self.posicoes = pd.concat([self.posicoes, novaPosicao.to_frame().T], ignore_index=True)
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
        sharpe = self.__calcular_sharpe(retornos_diarios, 'total_retorno', taxa_livre_risco_aa, freq='diária')

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

    def plotar_curva_capital_diario(self):
        plt.figure(figsize=(20,10))
        plt.plot(self.capital_diario.index, self.capital_diario['capital'], label='Capital Diário')
        plt.plot(self.capital_diario.index, self.capital_diario['media_movel_5d'], label='MM5 Capital', linestyle='--')
        plt.xlabel("Data")
        plt.ylabel("Lucro")
        plt.legend()
        plt.title('Evolução do Capital Diário')  # Título do gráfico
        plt.grid(True)  # Adicionar grade
        plt.show()

    def __calcular_sharpe(self, df, coluna_retorno, taxa_livre_risco_anual, freq='diária'):
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

    def arredondar_casas_decimais(self, casas=2):
        self.patrimonio["liquido"] = self.patrimonio["liquido"].astype(float).round(casas)
        self.patrimonio["saldo"] = self.patrimonio["saldo"].astype(float).round(casas)
        self.patrimonio["capital"] = self.patrimonio["capital"].astype(float).round(casas)
        self.operacoes["preco"] = self.operacoes["preco"].astype(float).round(casas)
        self.posicoes["precoEntrada"] = self.posicoes["precoEntrada"].astype(float).round(casas)
        self.posicoes["precoSaida"] = self.posicoes["precoSaida"].astype(float).round(casas)
        self.posicoes["forcaRelativa"] = self.posicoes["forcaRelativa"].astype(float).round(casas)
        self.posicoes["stopLoss"] = self.posicoes["stopLoss"].astype(float).round(casas)
