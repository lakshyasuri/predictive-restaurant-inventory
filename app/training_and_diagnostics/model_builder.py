import pandas as pd
from itertools import product
from skforecast.sarimax._sarimax import Sarimax
import numpy as np
from sklearn.metrics import mean_squared_error
from pmdarima.arima import auto_arima
from typing import Union
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import os
import joblib

pd.set_option("display.max.columns", None)


class ModelBuilder:
    def __init__(self, data: pd.DataFrame):
        self.model = None
        self.data = data
        self.training_data = None
        self.testing_data = None

    def set_training_testing_split(self, training_end_dt: str, testing_start_dt: str):
        self.training_data = self.data.loc[:pd.to_datetime(training_end_dt)].copy()
        self.testing_data = self.data.loc[pd.to_datetime(testing_start_dt):].copy()

    def set_time_series_index(self, col_name: str, frequency=None, method=None):
        frequency = "D" if None else frequency
        data = self.data.set_index(pd.to_datetime(self.data[col_name])).resample(frequency)
        data = data.first() if frequency == 'D' else data.sum()
        data = data.sort_index()
        date_range = pd.date_range(start=min(data.index), end=max(data.index), freq='D')
        missing_dates = date_range[~date_range.isin(data.index)]
        if not missing_dates.empty:
            print("Found missing dates in the time series data:\n", missing_dates)
            data = data.reindex(date_range)
            if method == "ffill":
                data.ffill(inplace=True)
            elif method == "bfill":
                data.bfill(inplace=True)
            elif method == "linear":
                data.interpolate(method="linear", inplace=True)
            elif not method:
                data.fillna(0, inplace=True)
            print(f"missing dates filled using {0 if not method else method}")
        print(data[data.index.duplicated])
        data = data.resample(frequency).sum().sort_index()
        self.data = data

    def choosing_sarima_model(self, col_name: str) -> tuple[tuple, float]:
        param_grid = {
            "p": [0, 1, 2, 3],
            "d": [0],
            "q": [0, 1, 2, 3],
            "P": [0, 1, 2, 3],
            "D": [0],
            "Q": [0, 1, 2, 3],
            "S": [7]
        }
        params = list(product(param_grid["p"], param_grid["d"], param_grid["q"],
                              param_grid["P"], param_grid["D"], param_grid["Q"], param_grid["S"]))
        results = []
        for param in params:
            try:
                # Define and fit SARIMAX model
                model = Sarimax(order=(param[0], param[1], param[2]),
                                seasonal_order=(param[3], param[4], param[5], param[6]))
                model.fit(y=self.training_data[col_name])

                # Make predictions
                predictions = model.predict(steps=len(self.testing_data[col_name]))

                # Calculate the root mean squared error
                rmse = np.sqrt(mean_squared_error(self.testing_data[col_name], predictions))

                # Store parameters and corresponding RMSE
                results.append((param, rmse))
            except Exception as e:
                print(f"Error for parameters {param}: {e}")
                continue
        best_param, best_rmse = min(results, key=lambda x: x[1])
        print("Best Parameters:", best_param)
        print("Best RMSE:", best_rmse)
        return best_param, best_rmse

    def choosing_sarima_w_auto_arima(self, col_name: str) -> tuple[tuple, tuple]:
        # choosing a Sarima model using the auto_arima process (AIC)
        model = auto_arima(self.training_data[col_name], start_p=0, start_q=0, d=0, max_p=5, max_q=5, max_d=1, m=7,
                           start_P=0, start_Q=0, D=0, max_D=1, max_P=5, max_Q=5, seasonal=True,
                           information_criterion='aic', trace=True)
        print(model.summary())
        return model.get_params()["order"], model.get_params()["seasonal_order"]

    def build_sarima_model(self, col_name: str, order: Union[tuple, None] = None,
                           seasonal_order: Union[tuple, None] = None,
                           method: Union[tuple, str] = None, data: Union[pd.Series, None] = None):
        if not order or not seasonal_order:
            if method is None:
                raise Exception("Method to determine the best SARIMA model not specified!")
            print(f"SARIMA model parameters not specified. Deciding the best ones using method: {method}")
            if method == "auto_arima":
                order, seasonal_order = self.choosing_sarima_w_auto_arima(col_name=col_name)
            elif method == "skforecast":
                params = self.choosing_sarima_model(col_name=col_name)
                order, seasonal_order = params[:3], params[3:]
        sarima_model = Sarimax(order=order, seasonal_order=seasonal_order)
        data = self.training_data[col_name] if data is None else data
        sarima_model.fit(y=data)
        self.model = sarima_model

    def test_model(self, col_name, start_idx: Union[None, int] = None, end_idx: Union[None, int] = None):
        start_idx = self.training_data.shape[0] if start_idx is None else start_idx
        end_idx = self.data.shape[0] - 1 if end_idx is None else end_idx
        predict_args = {"steps": len(self.testing_data)} if isinstance(self.model, Sarimax) else {"start": start_idx,
                                                                                                  "end": end_idx}
        predictions = self.model.predict(**predict_args)
        rmse = np.sqrt(mean_squared_error(self.testing_data[col_name], predictions))
        return predictions, rmse

    def save_model(self, path: str, filename: str):
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
        joblib.dump(self.model, os.path.join(path, f"{filename}.pkl"))
        print(f"model saved. Path: {os.path.join(path, filename)}.pkl")

    def load_model(self, path: str):
        self.model = joblib.load(path)

    def build_holt_winters_model(self, col_name: str, seasonality: str, seasonal_periods: int, trend: str,
                                 data: Union[pd.Series, None] = None, **kwargs):
        params = {"seasonal": seasonality, "seasonal_periods": seasonal_periods, "trend": trend, **kwargs}
        data = self.training_data[col_name] if data is None else data
        self.model = ExponentialSmoothing(data, **params).fit()

    def train_complete_holt_winters_model(self, col_name: str, seasonality: str, seasonal_periods: int, trend: str,
                                          **kwargs):
        data = self.data[col_name]
        self.build_holt_winters_model(col_name=col_name, seasonality=seasonality, seasonal_periods=seasonal_periods,
                                      trend=trend, data=data)

    def train_complete_sarima_model(self, col_name: str, order: tuple, seasonal_order: tuple):
        data = self.data[col_name]
        self.build_sarima_model(col_name=col_name, order=order, seasonal_order=seasonal_order, data=data)
