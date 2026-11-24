#!/usr/bin/env python3
"""
Clasificador binario de correos: SPAM (1) vs BUENO (0)

  - Bolsa de palabras : CountVectorizer (cuenta cuántas veces aparece cada palabra)
  - Red neuronal      : MLPClassifier con varias capas ocultas

Instalación (una sola librería):
    pip install scikit-learn

Para abrir .rar se necesita una herramienta del sistema: unrar, 7z o bsdtar.

Uso:
    python clasificador_spam.py entrenar  datos.rar
    python clasificador_spam.py clasificar correo
    python clasificador_spam.py clasificar nuevos.rar     (o una carpeta)

Estructura del .rar:
    easy_ham/  -> correos buenos (0)
    spam/      -> correos spam   (1)
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

import joblib
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier

MODELO = "modelo_spam.joblib"
CAPAS_OCULTAS = (256, 128, 64)     # 3 capas ocultas; ajusta si lo necesitas


# ---------------------------------------------------------------- lectura ---
def extraer_rar(ruta_rar, destino):
    comandos = [
        ("unrar", ["unrar", "x", "-y", "-inul", ruta_rar, destino + os.sep]),
        ("7z", ["7z", "x", "-y", "-o" + destino, ruta_rar]),
        ("bsdtar", ["bsdtar", "-xf", ruta_rar, "-C", destino]),
    ]
    for nombre, cmd in comandos:
        if shutil.which(nombre) and subprocess.run(cmd, capture_output=True).returncode == 0:
            return
    sys.exit("No pude extraer el .rar. Instala 'unrar', '7z' o 'bsdtar'.")


def leer_carpeta(carpeta):
    """[(ruta_relativa, texto)] de todos los archivos de una carpeta."""
    salida = []
    for raiz, _, archivos in os.walk(carpeta):
        for nombre in archivos:
            if nombre.startswith("cmds"):          # archivo de control del corpus
                continue
            ruta = os.path.join(raiz, nombre)
            with open(ruta, "rb") as f:
                salida.append((os.path.relpath(ruta, carpeta), f.read().decode("latin-1")))
    return salida


def cargar(ruta):
    """Acepta un .rar, una carpeta o un solo correo."""
    if ruta.lower().endswith(".rar"):
        tmp = tempfile.mkdtemp()
        try:
            extraer_rar(ruta, tmp)
            return leer_carpeta(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if os.path.isdir(ruta):
        return leer_carpeta(ruta)
    with open(ruta, "rb") as f:
        return [(os.path.basename(ruta), f.read().decode("latin-1"))]


def etiqueta(ruta_rel):
    """1 = spam, 0 = bueno, None = desconocido (según la carpeta)."""
    partes = ruta_rel.lower().replace("\\", "/").split("/")[:-1]
    if "spam" in partes:
        return 1
    if any("ham" in p for p in partes):
        return 0
    return None


def preparar_texto(correo):
    """Quita encabezados técnicos: se queda con Subject + cuerpo (sin HTML ni URLs)."""
    cabecera, _, cuerpo = correo.partition("\n\n")
    m = re.search(r"^Subject:(.*)$", cabecera, re.M | re.I)
    texto = (m.group(1) if m else "") + " " + cuerpo
    texto = re.sub(r"<[^>]+>", " ", texto)
    return re.sub(r"https?://\S+", " urltoken ", texto)


# --------------------------------------------------------------- comandos ---
def entrenar(ruta):
    print("Leyendo correos ...")
    datos = [(t, etiqueta(r)) for r, t in cargar(ruta)]
    datos = [(preparar_texto(t), y) for t, y in datos if y is not None]
    textos = [t for t, _ in datos]
    y = [e for _, e in datos]
    if len(set(y)) < 2:
        sys.exit("Se necesitan correos de las DOS carpetas (easy_ham y spam).")
    print(f"  Buenos: {y.count(0)} | Spam: {y.count(1)}")

    X_tr_txt, X_te_txt, y_tr, y_te = train_test_split(
        textos, y, test_size=0.2, random_state=42, stratify=y
    )

    # Bolsa de palabras: matriz (correos x palabras) con el conteo de cada palabra
    vec = CountVectorizer(
        lowercase=True,
        token_pattern=r"[a-zA-Z]{3,}",   # solo palabras de 3+ letras
        stop_words="english",            # quita "the", "and", ...
        max_features=5000,               # las 5000 palabras más frecuentes
        min_df=3,                        # descarta palabras muy raras
    )
    X_tr = vec.fit_transform(X_tr_txt)
    X_te = vec.transform(X_te_txt)
    print(f"  Vocabulario: {len(vec.vocabulary_)} palabras")

    print(f"Entrenando red neuronal {CAPAS_OCULTAS} ...")
    red = MLPClassifier(
        hidden_layer_sizes=CAPAS_OCULTAS,
        activation="relu",
        early_stopping=True,      # se detiene cuando deja de mejorar
        random_state=42,
        max_iter=200,
    )
    red.fit(X_tr, y_tr)

    pred = red.predict(X_te)
    print("\n=== Resultados en correos de prueba (no vistos en el entrenamiento) ===")
    print(classification_report(y_te, pred, target_names=["bueno", "spam"], digits=3))
    print("Matriz de confusión [filas = real, columnas = predicho]:")
    print(confusion_matrix(y_te, pred))

    joblib.dump({"vec": vec, "red": red}, MODELO)
    print(f"\nModelo guardado en {MODELO}")


def predecir(ruta, ruta_modelo=MODELO):
    if not os.path.exists(ruta_modelo):
        raise FileNotFoundError(
            "Primero entrena el modelo: python spam_detector.py entrenar datos.rar"
        )
    m = joblib.load(ruta_modelo)
    correos = cargar(ruta)
    if not correos:
        raise ValueError("No se encontraron correos para clasificar.")
    X = m["vec"].transform([preparar_texto(t) for _, t in correos])
    pred = m["red"].predict(X)
    prob = m["red"].predict_proba(X)

    return [
        (nombre, "SPAM" if p == 1 else "BUENO", float(pr[p]))
        for (nombre, _), p, pr in zip(correos, pred, prob)
    ]


def clasificar(ruta):
    try:
        resultados = predecir(ruta)
    except FileNotFoundError as error:
        sys.exit(str(error))

    for nombre, etiqueta_predicha, confianza in resultados:
        print(f"{nombre}: {etiqueta_predicha} ({confianza * 100:.1f}%)")
    spam = sum(etiqueta_predicha == "SPAM" for _, etiqueta_predicha, _ in resultados)
    print(f"\nResumen: {spam} spam | {len(resultados) - spam} buenos")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("entrenar", "clasificar"):
        print(__doc__)
        sys.exit(1)
    if not os.path.exists(sys.argv[2]):
        sys.exit(f"No existe: {sys.argv[2]}")
    (entrenar if sys.argv[1] == "entrenar" else clasificar)(sys.argv[2])