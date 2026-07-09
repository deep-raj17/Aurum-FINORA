import torch
import yfinance
import pandas
import numpy
import sklearn
import xgboost
import lightgbm
import catboost
import transformers
import datasets
import accelerate
import pytorch_lightning
import optuna
import ta
import statsmodels
import mlflow

print("=" * 60)
print("Python OK")
print("Torch:", torch.__version__)
print("CUDA Available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

print("=" * 60)
print("All libraries imported successfully.")