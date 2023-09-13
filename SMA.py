# -*- coding: utf-8 -*-
"""
Created on Sun Jun 18 13:32:15 2023

@author: tt935
"""


import shioaji as sj
import pandas as pd
import datetime
from datetime import date, timedelta
import talib
import matplotlib.pyplot as plt
import numpy as np
# 建立 Shioaji api 物件
api = sj.Shioaji(simulation=True)


def login():
    accounts = api.login(
        api_key="YOUR API KEY",
        secret_key="YOUR secret_key",
        fetch_contract=True,
        contracts_cb=lambda security_type: print(
            f"{repr(security_type)} fetch done.")
    )
    return accounts

# 匯入憑證


def activate_ca():
    result = api.activate_ca(
        ca_path="YOUR CA PATH",
        ca_passwd="YOUR ACCOUNT ID",
        person_id="YOUR ACCOUNT ID",
    )
    print(result)
    return result


def activate_login():
    accounts = login()
    if accounts:
        result = activate_ca()
        if result:
            print("登入成功")
        else:
            print("登入失敗")
    else:
        print("登入失敗")


def getcontract():
    symbol = input("請輸入股票代號 :")
    the_type = input("請輸入種類 :")  # 輸入stocks or future 均為小寫
    if the_type == "stocks":
        return api.Contracts.Stocks[symbol]
    elif the_type == "future":
        return api.Contracts.Future[symbol]
    else:
        print("Not included in contracts")


def getticks(
        api,
        contract,
        timeout=100000,
        Enable_print=False
):
    start = input("請輸入開始回測日期 :")
    end = input("請輸入結束回測日期 :")
    enddate = datetime.datetime.strptime(end, "%Y-%m-%d").date()
    startdate = datetime.datetime.strptime(start, "%Y-%m-%d").date()

    list_ticks = []
    while enddate != startdate:
        if timeout > 0:
            ticks = api.ticks(contract=contract,
                              date=str(startdate),
                              timeout=timeout)
        else:
            ticks = api.ticks(contract=contract,
                              date=str(startdate),
                              timeout=timeout)
        df_ticks = pd.DataFrame({**ticks})
        df_ticks.index = pd.to_datetime(df_ticks.ts)
        df_ticks = df_ticks.groupby(df_ticks.index).first()
        list_ticks.append(df_ticks)
        startdate = startdate + datetime.timedelta(days=1)
    if len(list_ticks) > 0:
        df_ticks_concat = pd.concat(list_ticks)
        df_ticks_concat = df_ticks_concat.drop(columns="ts")
    else:
        df_ticks_concat = []
    return df_ticks_concat


def tickstobar(ticks):
    period = input("請輸入時間頻率 :")  # 5min
    kbars_out = pd.DataFrame(
        columns=["close", "high", "low", "open", "volume"])
    kbars_out["close"] = ticks["close"].resample(period).last()
    kbars_out["high"] = ticks["close"].resample(period).max()
    kbars_out["low"] = ticks["close"].resample(period).min()
    kbars_out["open"] = ticks["close"].resample(period).first()
    kbars_out["volume"] = ticks["volume"].resample(period).sum()
    kbars_out = kbars_out.dropna()
    return kbars_out


activate_login()
data_ticks = tickstobar(getticks(api, contract=getcontract()))
close_price = data_ticks["close"]
open_price = data_ticks["open"]
lowest_price = min(data_ticks["low"])
Tradingcost = (0.4 / 100)


def createmasignal(close_p, periodshort, periodlong):
    result = pd.DataFrame()
    for shortday in periodshort:
        for longday in periodlong:
            if shortday >= longday:
                continue
            shortma = talib.SMA(close_p, shortday)
            longma = talib.SMA(close_p, longday)
            key = f"{shortday},{longday}"
            signal = shortma > longma
            result["open"] = open_price
            result[key] = signal
    return result


def calculate_return(close_p, signal, open_p):
    position = 0
    buy = 0
    sell = 0
    returns = []
    equity_curve = []
    peak = 0
    record_low = 0
    record = 0
    mdd = 0
    for i in range(1, close_p.shape[0]-1):
        if position == 0 and signal[i] == True:  # 進場
            position = 1
            buy = open_p[i+1]*1000 + ((open_p[i+1]*1000)*Tradingcost)  # 紀錄總成本
        elif position == 1 and signal[i] == True:  # 進場中間資金最大回落
            record = close_p[i]
            if record_low == 0:
                record_low = record
            if record_low > record:
                record_low = record

        elif position == 1 and signal[i] == False:  # 出場
            position = 0
            sell = open_p[i+1]*1000
            returns.append((sell - buy) / buy)  # 單次報酬率
            equity_curve.append(sell)
            if sell > peak:
                peak = sell  # 紀錄賣出最高點
            if (peak - (record_low*1000)) / peak > mdd:  # 回測拉回最高至最低的Range
                mdd = (peak - (record_low*1000)) / peak

    avg_return = np.mean(returns)
    max_drawdown = mdd

    return avg_return, max_drawdown


def optimize_backtest(close_p, periodshort_range, periodlong_range, open_p):
    best_return = -float("inf")
    best_mdd = float("inf")
    best_parameters = {}

    for shortday in periodshort_range:
        for longday in periodlong_range:
            if shortday >= longday:
                continue

            signals = createmasignal(close_p, [shortday], [longday])
            buy_signal = signals.iloc[:, -1].values
            avg_return, max_drawdown = calculate_return(
                close_p, buy_signal, open_p)

            if avg_return > best_return and max_drawdown < best_mdd:
                best_return = avg_return
                best_mdd = max_drawdown
                best_parameters = {"shortday": shortday, "longday": longday}

    return best_parameters, best_return, best_mdd


def main():
    periodshort_range = np.arange(5, 40, 5)
    periodlong_range = np.arange(5, 40, 5)

    best_parameters, best_return, best_mdd = optimize_backtest(
        close_price, periodshort_range, periodlong_range, open_price)

    print(f"Best Parameters: {best_parameters}")
    print(f"Best Average Return: {best_return}")
    print(f"Best Whole Return: {best_mdd}")


if __name__ == "__main__":
    main()
