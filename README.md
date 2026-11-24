# proyectoFinalIa2

## Clasificador visual

La interfaz de escritorio permite seleccionar un correo `.txt` o `.eml` y ver
si el modelo lo clasifica como `SPAM` o `BUENO`, junto con su porcentaje
estimado.

1. Instala la dependencia desde PowerShell:

   ```powershell
   python -m pip install scikit-learn
   ```

2. Desde esta carpeta, entrena el modelo si aún no existe:

   ```powershell
   python spam_detector.py entrenar .\correos.rar
   ```

3. Abre la interfaz:

   ```powershell
   python spam_gui.py
   ```

En la ventana, selecciona un correo individual y pulsa **Clasificar**. Para
entrenar desde un `.rar`, también necesitas `unrar`, `7z` o `bsdtar` disponible
en el `PATH`.