# train_model.py
# Hybrid trainer: prefer real data (data/records.csv). If too few rows, augment with synthetic samples.
# Produces models/model.joblib and models/sample_training_data.csv
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor #ml library multiple decision tree 
from sklearn.preprocessing import OneHotEncoder #categorical data to numeical convert
from sklearn.compose import ColumnTransformer  #-- pipeline add
from sklearn.pipeline import Pipeline # -- pipeline 
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

os.makedirs('models', exist_ok=True)
os.makedirs('data', exist_ok=True)

MIN_REAL = 100     # if real rows < MIN_REAL, augment with synthetic data
TARGET_SIZE = 2000 # total rows after augmentation (approx)

def make_synthetic_rows(n):
    rng = np.random.RandomState(42)
    services = ['Painting','Plumbing','Tiles','Carpentry','AC Service','Renovation']
    rows = []
    for _ in range(n):
        svc = rng.choice(services, p=[0.35,0.15,0.2,0.1,0.1,0.1])
        area = float(max(0.0, rng.normal(loc=50 if svc in ['Painting','Tiles','Renovation'] else 10, scale=30)))
        points = int(rng.poisson(1) if svc=='Plumbing' else 0)
        image_flag = int(rng.choice([0,1], p=[0.8,0.2]))
        if svc == 'Painting':
            material = area * 12 * 1.0
            labour = area * 30
        elif svc == 'Tiles':
            material = area * 600 * 1.05
            labour = area * 50
        elif svc == 'Plumbing':
            material = points * 200
            labour = 500 + points * 300
        elif svc == 'Carpentry':
            material = area * 150
            labour = area * 80
        elif svc == 'AC Service':
            material = 0
            labour = 900
        else: # Renovation
            material = area * 200
            labour = area * 120
        noise = rng.normal(0, 0.05 * (material + labour))
        total = float(max(100, material + labour + noise + (100 if image_flag else 0)))
        rows.append([svc, area, points, image_flag, total])
    return pd.DataFrame(rows, columns=['service','area','points','image','total'])

# 1) Load real data if present
real_path = os.path.join('data','records.csv')
if os.path.exists(real_path):
    try:
        df_real = pd.read_csv(real_path)
        # keep only required columns if they exist
        expected = ['service','area','points','image','total']
        df_real = df_real[[c for c in expected if c in df_real.columns]].copy()
        # ensure columns exist
        for c in expected:
            if c not in df_real.columns:
                df_real[c] = 0
        # coerce types
        df_real['area'] = pd.to_numeric(df_real['area'], errors='coerce').fillna(0.0)
        df_real['points'] = pd.to_numeric(df_real['points'], errors='coerce').fillna(0).astype(int)
        df_real['image'] = pd.to_numeric(df_real['image'], errors='coerce').fillna(0).astype(int)
        df_real['total'] = pd.to_numeric(df_real['total'], errors='coerce').fillna(df_real['total'].median() if not df_real['total'].empty else 0.0)
        print(f"Loaded real records: {len(df_real)} rows from {real_path}")
    except Exception as e:
        print("Failed to read real records:", e)
        df_real = pd.DataFrame(columns=['service','area','points','image','total'])
else:
    df_real = pd.DataFrame(columns=['service','area','points','image','total'])
    print("No real records file found; using synthetic data.")

# 2) Decide dataset composition
n_real = len(df_real)
if n_real >= MIN_REAL:
    df = df_real.copy()
    print(f"Using {n_real} real rows for training (>= {MIN_REAL}).")
else:
    need = max(0, TARGET_SIZE - n_real)
    print(f"Only {n_real} real rows found (< {MIN_REAL}). Augmenting with {need} synthetic rows to reach ~{TARGET_SIZE}.")
    df_synth = make_synthetic_rows(need)
    # concat real first so model sees real examples; then synthetic
    df = pd.concat([df_real, df_synth], ignore_index=True)
    print(f"Training rows: {len(df)} (real: {n_real}, synthetic: {len(df_synth)})")

# sanity clean: drop any rows with missing total
df = df.dropna(subset=['total'])
df = df.reset_index(drop=True)

# 3) prepare features and pipeline
X = df[['service','area','points','image']]
y = df['total']

categorical_features = ['service']
numeric_features = ['area','points','image']

preprocessor = ColumnTransformer(
    transformers=[
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features),
    ],
    remainder='passthrough'  # keep numeric as-is
)

pipeline = Pipeline([
    ('pre', preprocessor),
    ('model', RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1))
])

# 4) train / evaluate
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.18, random_state=42)
print(f"Training on {len(X_train)} rows; validating on {len(X_test)} rows...")
pipeline.fit(X_train, y_train)
y_pred = pipeline.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)
print(f"Validation MAE: {mae:.2f}   R2: {r2:.4f}")

# 5) save model & sample data
joblib.dump(pipeline, os.path.join('models','model.joblib'))
print("Saved model to models/model.joblib")
# save a small sample of training data for inspection
df.sample(min(200, len(df))).to_csv(os.path.join('models','sample_training_data.csv'), index=False)
print("Saved sample training rows to models/sample_training_data.csv")
