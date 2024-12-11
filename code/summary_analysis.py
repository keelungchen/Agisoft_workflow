import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import numpy as np

# Load CSV data
file_path = r"D:\\3D_workshop\\indoor_demo\\summary_results.csv"
data = pd.read_csv(file_path)

# Clean and preprocess data
data['Tie Points'] = data['Tie Points'].str.replace(',', '').astype(float)

# Scatter plot of Flying Altitude vs Ground Resolution with R2
plt.figure(figsize=(10, 6))
plt.scatter(data['Flying Altitude'], data['Ground Resolution'], color='blue', label='Data Points')

# Linear regression for R2
X = data['Flying Altitude'].values.reshape(-1, 1)
Y = data['Ground Resolution'].values
model = LinearRegression()
model.fit(X, Y)
Y_pred = model.predict(X)
r2 = r2_score(Y, Y_pred)
plt.plot(data['Flying Altitude'], Y_pred, color='red', label=f'Linear Fit (R2 = {r2:.2f})')

plt.title('Flying Altitude vs Ground Resolution')
plt.xlabel('Flying Altitude (m)')
plt.ylabel('Ground Resolution (cm)')
plt.legend()
plt.grid()
plt.show()

# Comparison of different Folder Names across metrics
metrics = ['Camera Stations', 'Flying Altitude', 'Ground Resolution', 'Coverage Area', 'Reprojection Error', 'Tie Points', 'Scale Bar Error']

for metric in metrics:
    plt.figure(figsize=(10, 6))
    sns.barplot(x='Folder Name', y=metric, data=data)
    plt.title(f'Comparison of {metric}')
    plt.ylabel(metric)
    plt.xlabel('Folder Name')
    plt.xticks(rotation=45)
    plt.grid(axis='y')
    plt.show()
