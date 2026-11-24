import csv
import email
import re
import tkinter as tk
from datetime import datetime
from email import policy
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from spam_detector import MODELO, predecir


BASE_DIR = Path(__file__).resolve().parent
RUTA_MODELO = BASE_DIR / MODELO

# ------------------------------------------------------------------ estilo ---
BG = "#F1F5F9"
CARD = "#FFFFFF"
DARK = "#0F172A"
PRIMARY = "#2563EB"
PRIMARY_DARK = "#1D4ED8"
TEXT = "#1E293B"
MUTED = "#64748B"
BORDER = "#E2E8F0"
SPAM = "#DC2626"
SPAM_BG = "#FEE2E2"
OK = "#16A34A"
OK_BG = "#DCFCE7"
NEUTRAL_BG = "#F8FAFC"

FUENTE = "Segoe UI"
F_TITULO = (FUENTE, 20, "bold")
F_SECCION = (FUENTE, 11, "bold")
F_NORMAL = (FUENTE, 10)
F_BOLD = (FUENTE, 10, "bold")
F_PEQ = (FUENTE, 9)
F_NUM = (FUENTE, 15, "bold")
F_VEREDICTO = (FUENTE, 22, "bold")


# ----------------------------------------------------------------- lógica ---
def es_spam(etiqueta):
    e = str(etiqueta).lower()
    negativos = ("no spam", "no es", "not", "ham", "bueno", "legit")
    return "spam" in e and not any(n in e for n in negativos)


def formatear_bytes(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.1f} MB"


def leer_correo(ruta):
    """Extrae metadatos y un resumen del correo para mostrarlos en pantalla."""
    datos = Path(ruta).read_bytes()
    try:
        texto = datos.decode("utf-8")
    except UnicodeDecodeError:
        texto = datos.decode("latin-1")

    info = {
        "remitente": "—", "destinatario": "—", "asunto": "—", "fecha": "—",
        "cuerpo": "", "html": False, "adjuntos": 0,
    }
    try:
        msg = email.message_from_string(texto, policy=policy.default)
        for clave, campo in (("remitente", "From"), ("destinatario", "To"),
                             ("asunto", "Subject"), ("fecha", "Date")):
            if msg[campo]:
                info[clave] = str(msg[campo]).replace("\n", " ").strip()
        parte = msg.get_body(preferencelist=("plain", "html"))
        if parte is not None:
            info["cuerpo"] = parte.get_content()
            info["html"] = parte.get_content_type() == "text/html"
        info["adjuntos"] = sum(1 for p in msg.walk() if p.get_filename())
    except Exception:
        pass

    if not info["cuerpo"]:
        info["cuerpo"] = texto.partition("\n\n")[2] or texto
    cuerpo = info["cuerpo"]
    if info["html"]:
        cuerpo = re.sub(r"<[^>]+>", " ", cuerpo)
    cuerpo = cuerpo.strip()

    info["cuerpo"] = cuerpo
    info["bytes"] = len(datos)
    info["palabras"] = len(re.findall(r"\w+", cuerpo))
    info["urls"] = len(re.findall(r"https?://", texto, re.I))
    return info


# ------------------------------------------------------------- aplicación ---
class SpamDetectorApp:
    def __init__(self, root):
        self.root = root
        self.ruta_correo = None
        self.info_correo = None
        self.historial = []
        self.total = self.total_spam = 0

        root.title("Detector de correo SPAM")
        root.geometry("1040x870")
        root.minsize(940, 800)
        root.configure(bg=BG)

        self._estilos()
        self._cabecera()
        self._barra_estado()
        self._panel_historial(root)

        cuerpo = tk.Frame(root, bg=BG)
        cuerpo.pack(fill="both", expand=True, padx=20, pady=(16, 0))
        cuerpo.columnconfigure(0, weight=3, uniform="col")
        cuerpo.columnconfigure(1, weight=2, uniform="col")
        cuerpo.rowconfigure(0, weight=1)

        izq = tk.Frame(cuerpo, bg=BG)
        izq.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        der = tk.Frame(cuerpo, bg=BG)
        der.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._panel_correo(izq)
        self._panel_resultado(der)
        self._panel_modelo(der)

        self.actualizar_modelo()
        self.estado("Listo. Selecciona un correo para comenzar.")

        root.update_idletasks()
        x = (root.winfo_screenwidth() - root.winfo_width()) // 2
        y = (root.winfo_screenheight() - root.winfo_height()) // 2
        root.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------- piezas ---
    def _estilos(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Primary.TButton", font=F_BOLD, background=PRIMARY,
                    foreground="white", borderwidth=0, focusthickness=0,
                    padding=(20, 10))
        s.map("Primary.TButton",background=[("disabled", "#BFD0F5"), ("active", PRIMARY_DARK)],foreground=[("disabled", "white")])
        s.configure("Sec.TButton", font=F_NORMAL, background=CARD,
                    foreground=TEXT, bordercolor=BORDER, lightcolor=CARD,
                    darkcolor=CARD, focusthickness=0, padding=(16, 9))
        s.map("Sec.TButton", background=[("active", "#EEF2FF")])
        s.configure("Treeview", font=F_NORMAL, rowheight=28, background=CARD,
                    fieldbackground=CARD, foreground=TEXT, borderwidth=0)
        s.configure("Treeview.Heading", font=F_BOLD, background="#F1F5F9",
                    foreground=MUTED, relief="flat", padding=(8, 6))
        s.map("Treeview", background=[("selected", "#DBEAFE")],foreground=[("selected", TEXT)])
        s.configure("Vertical.TScrollbar", background=BORDER, troughcolor=CARD,
                    bordercolor=CARD, arrowcolor=MUTED)

    def _cabecera(self):
        barra = tk.Frame(self.root, bg=DARK)
        barra.pack(fill="x")
        izq = tk.Frame(barra, bg=DARK)
        izq.pack(side="left", padx=24, pady=16)
        tk.Label(izq, text="Detector de correo SPAM", font=F_TITULO,
                 bg=DARK, fg="white").pack(anchor="w")
        tk.Label(izq, text="Bolsa de palabras + red neuronal · clasificación binaria",
                 font=F_NORMAL, bg=DARK, fg="#94A3B8").pack(anchor="w")

        self.badge = tk.Label(barra, font=F_BOLD, padx=14, pady=6)
        self.badge.pack(side="right", padx=24)

    def _card(self, parent, titulo, expand=False, pady=(0, 12)):
        marco = tk.Frame(parent, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1)
        marco.pack(fill="both" if expand else "x", expand=expand, pady=pady)
        tk.Label(marco, text=titulo.upper(), font=(FUENTE, 8, "bold"),
                 bg=CARD, fg=MUTED).pack(anchor="w", padx=16, pady=(12, 0))
        interior = tk.Frame(marco, bg=CARD)
        interior.pack(fill="both", expand=True, padx=16, pady=(6, 14))
        return interior

    def _panel_correo(self, padre):
        c = self._card(padre, "1 · Correo a analizar", expand=True, pady=0)

        fila = tk.Frame(c, bg=CARD)
        fila.pack(fill="x")
        ttk.Button(fila, text="Seleccionar correo…", style="Sec.TButton",
                   command=self.seleccionar_correo).pack(side="left")
        self.boton_clasificar = ttk.Button(
            fila, text="Clasificar", style="Primary.TButton",
            command=self.clasificar_correo, state="disabled")
        self.boton_clasificar.pack(side="left", padx=10)

        self.archivo_var = tk.StringVar(value="Ningún archivo seleccionado")
        tk.Label(c, textvariable=self.archivo_var, font=F_PEQ, bg=CARD,
                 fg=MUTED, anchor="w", justify="left", wraplength=520
                 ).pack(fill="x", pady=(8, 10))

        # metadatos
        self.meta = {}
        tabla = tk.Frame(c, bg=NEUTRAL_BG, highlightbackground=BORDER,
                         highlightthickness=1)
        tabla.pack(fill="x")
        tabla.columnconfigure(1, weight=1)
        for i, (etq, clave) in enumerate((("De", "remitente"), ("Para", "destinatario"),
                                          ("Asunto", "asunto"), ("Fecha", "fecha"))):
            tk.Label(tabla, text=etq, font=F_BOLD, bg=NEUTRAL_BG, fg=MUTED,
                     width=7, anchor="w").grid(row=i, column=0, padx=(12, 0), pady=3)
            var = tk.StringVar(value="—")
            tk.Label(tabla, textvariable=var, font=F_NORMAL, bg=NEUTRAL_BG,
                     fg=TEXT, anchor="w", justify="left", wraplength=430
                     ).grid(row=i, column=1, sticky="w", padx=8, pady=3)
            self.meta[clave] = var

        # métricas
        fila = tk.Frame(c, bg=CARD)
        fila.pack(fill="x", pady=12)
        self.chips = {}
        for i, (clave, etq) in enumerate((("bytes", "Tamaño"), ("palabras", "Palabras"),
                                          ("urls", "Enlaces"), ("adjuntos", "Adjuntos"),
                                          ("formato", "Formato"))):
            fila.columnconfigure(i, weight=1, uniform="chip")
            caja = tk.Frame(fila, bg=NEUTRAL_BG, highlightbackground=BORDER,
                            highlightthickness=1)
            caja.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 4, 0))
            var = tk.StringVar(value="—")
            tk.Label(caja, textvariable=var, font=(FUENTE, 12, "bold"),
                     bg=NEUTRAL_BG, fg=TEXT).pack(pady=(8, 0))
            tk.Label(caja, text=etq, font=F_PEQ, bg=NEUTRAL_BG, fg=MUTED
                     ).pack(pady=(0, 8))
            self.chips[clave] = var

        tk.Label(c, text="Vista previa del contenido", font=F_BOLD, bg=CARD,
                 fg=TEXT).pack(anchor="w", pady=(2, 4))
        marco = tk.Frame(c, bg=CARD)
        marco.pack(fill="both", expand=True)
        self.vista = tk.Text(marco, wrap="word", height=8, font=("Consolas", 10),
                             bg=NEUTRAL_BG, fg=TEXT, relief="flat", padx=10,
                             pady=8, highlightbackground=BORDER,
                             highlightthickness=1, state="disabled")
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.vista.yview)
        self.vista.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.vista.pack(side="left", fill="both", expand=True)

    def _panel_resultado(self, padre):
        c = self._card(padre, "2 · Resultado")
        self.caja_res = tk.Frame(c, bg=NEUTRAL_BG, highlightbackground=BORDER,
                                 highlightthickness=1)
        self.caja_res.pack(fill="x")
        self.res_titulo = tk.Label(self.caja_res, text="Sin analizar",
                                   font=F_VEREDICTO, bg=NEUTRAL_BG, fg=MUTED)
        self.res_titulo.pack(pady=(10, 0))
        self.res_sub = tk.Label(self.caja_res,
                                text="Selecciona un correo y pulsa Clasificar",
                                font=F_NORMAL, bg=NEUTRAL_BG, fg=MUTED)
        self.res_sub.pack(pady=(0, 6))

        self.medidor = tk.Canvas(self.caja_res, height=14, bg=NEUTRAL_BG,
                                 highlightthickness=0)
        self.medidor.pack(fill="x", padx=20, pady=(0, 6))
        self.medidor.bind("<Configure>", lambda e: self._dibujar_medidor())
        self.res_conf = tk.Label(self.caja_res, text="", font=F_BOLD,
                                 bg=NEUTRAL_BG, fg=MUTED)
        self.res_conf.pack(pady=(0, 10))
        self._valor_medidor, self._color_medidor = 0.0, BORDER

        # estadísticas de la sesión
        fila = tk.Frame(c, bg=CARD)
        fila.pack(fill="x", pady=(8, 0))
        self.stats = {}
        for i, (clave, etq) in enumerate((("total", "Analizados"), ("spam", "Spam"),
                                          ("buenos", "Buenos"), ("pct", "% Spam"))):
            fila.columnconfigure(i, weight=1, uniform="st")
            caja = tk.Frame(fila, bg=CARD)
            caja.grid(row=0, column=i)
            var = tk.StringVar(value="0")
            tk.Label(caja, textvariable=var, font=F_NUM, bg=CARD, fg=TEXT).pack()
            tk.Label(caja, text=etq, font=F_PEQ, bg=CARD, fg=MUTED).pack()
            self.stats[clave] = var

    def _panel_modelo(self, padre):
        c = self._card(padre, "Información del programa", expand=True, pady=0)
        self.modelo_vars = {}
        for etq, clave in (("Modelo", "nombre"), ("Estado", "estado"),
                           ("Detalles", "detalles")):
            fila = tk.Frame(c, bg=CARD)
            fila.pack(fill="x", pady=2)
            tk.Label(fila, text=etq, font=F_BOLD, bg=CARD, fg=MUTED, width=10,
                     anchor="w").pack(side="left")
            var = tk.StringVar(value="—")
            tk.Label(fila, textvariable=var, font=F_NORMAL, bg=CARD, fg=TEXT,
                     anchor="w").pack(side="left")
            self.modelo_vars[clave] = var

        tk.Frame(c, bg=BORDER, height=1).pack(fill="x", pady=6)
        explicacion = (
            "Ochoa Ortega Andrea J."
        )
        tk.Label(c, text=explicacion, font=F_PEQ, bg=CARD, fg=TEXT, justify="left",
                 anchor="nw", wraplength=360).pack(fill="x")

    def _panel_historial(self, padre):
        marco = tk.Frame(padre, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1)
        marco.pack(fill="x", side="bottom", padx=20, pady=16)
        cab = tk.Frame(marco, bg=CARD)
        cab.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(cab, text="HISTORIAL DE LA SESIÓN", font=(FUENTE, 8, "bold"),
                 bg=CARD, fg=MUTED).pack(side="left")
        ttk.Button(cab, text="Limpiar", style="Sec.TButton",
                   command=self.limpiar_historial).pack(side="right")
        ttk.Button(cab, text="Exportar CSV", style="Sec.TButton",
                   command=self.exportar_csv).pack(side="right", padx=8)

        cols = ("hora", "archivo", "asunto", "resultado", "confianza")
        self.tabla = ttk.Treeview(marco, columns=cols, show="headings", height=3)
        for col, txt, ancho in (("hora", "Hora", 80), ("archivo", "Archivo", 230),
                                ("asunto", "Asunto", 330), ("resultado", "Resultado", 110),
                                ("confianza", "Confianza", 90)):
            self.tabla.heading(col, text=txt)
            self.tabla.column(col, width=ancho, anchor="w")
        self.tabla.tag_configure("spam", background=SPAM_BG)
        self.tabla.tag_configure("ok", background=OK_BG)
        self.tabla.pack(fill="x", padx=16, pady=(0, 14))

    def _barra_estado(self):
        self.estado_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.estado_var, font=F_PEQ, bg=DARK,
                 fg="#CBD5E1", anchor="w", padx=16, pady=5).pack(fill="x", side="bottom")

    # ------------------------------------------------------------ helpers ---
    def estado(self, texto):
        self.estado_var.set(texto)

    def actualizar_modelo(self):
        if RUTA_MODELO.exists():
            st = RUTA_MODELO.stat()
            self.modelo_vars["nombre"].set(RUTA_MODELO.name)
            self.modelo_vars["estado"].set("Cargado y listo")
            fecha = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")
            self.modelo_vars["detalles"].set(f"{formatear_bytes(st.st_size)} · {fecha}")
            self.badge.configure(text="●  Modelo listo", bg="#14532D", fg="#BBF7D0")
        else:
            self.modelo_vars["nombre"].set(RUTA_MODELO.name)
            self.modelo_vars["estado"].set("No encontrado — entrena primero")
            self.modelo_vars["detalles"].set("—")
            self.badge.configure(text="●  Modelo no encontrado", bg="#7F1D1D",
                                 fg="#FECACA")

    def _dibujar_medidor(self):
        cv = self.medidor
        cv.delete("all")
        w = max(cv.winfo_width(), 10)
        cv.create_rectangle(0, 3, w, 11, fill=BORDER, outline="")
        if self._valor_medidor > 0:
            cv.create_rectangle(0, 3, w * self._valor_medidor, 11,
                                fill=self._color_medidor, outline="")

    def _mostrar_resultado(self, spam, confianza):
        color, fondo = (SPAM, SPAM_BG) if spam else (OK, OK_BG)
        nivel = "alta" if confianza >= 0.9 else "media" if confianza >= 0.7 else "baja"
        for w in (self.caja_res, self.res_titulo, self.res_sub, self.res_conf, self.medidor):
            w.configure(bg=fondo)
        self.res_titulo.configure(text="⚠  SPAM" if spam else "✔  CORREO BUENO", fg=color)
        self.res_sub.configure(
            text="Este correo parece no deseado." if spam
            else "Este correo parece legítimo.", fg=color)
        self.res_conf.configure(text=f"Confianza {nivel}: {confianza * 100:.1f}%", fg=color)
        self._valor_medidor, self._color_medidor = confianza, color
        self._dibujar_medidor()

    def _reiniciar_resultado(self):
        for w in (self.caja_res, self.res_titulo, self.res_sub, self.res_conf, self.medidor):
            w.configure(bg=NEUTRAL_BG)
        self.res_titulo.configure(text="Sin analizar", fg=MUTED)
        self.res_sub.configure(text="Pulsa Clasificar para analizar este correo", fg=MUTED)
        self.res_conf.configure(text="")
        self._valor_medidor = 0.0
        self._dibujar_medidor()

    def _actualizar_stats(self):
        self.stats["total"].set(str(self.total))
        self.stats["spam"].set(str(self.total_spam))
        self.stats["buenos"].set(str(self.total - self.total_spam))
        pct = (self.total_spam / self.total * 100) if self.total else 0
        self.stats["pct"].set(f"{pct:.0f}%")

    # ------------------------------------------------------------ acciones ---
    def seleccionar_correo(self):
        ruta = filedialog.askopenfilename(
            parent=self.root,
            title="Selecciona un correo",
            filetypes=[
                ("Correos de texto", "*.txt *.eml"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not ruta:
            return
        if Path(ruta).suffix.lower() == ".rar":
            messagebox.showwarning(
                "Formato no compatible",
                "Selecciona un solo correo de texto (.txt o .eml), no un archivo .rar.",
                parent=self.root,
            )
            return

        try:
            info = leer_correo(ruta)
        except OSError as error:
            messagebox.showerror("No se pudo abrir el archivo", str(error),
                                 parent=self.root)
            return

        self.ruta_correo, self.info_correo = ruta, info
        self.archivo_var.set(ruta)
        for clave, var in self.meta.items():
            var.set(info[clave])
        self.chips["bytes"].set(formatear_bytes(info["bytes"]))
        self.chips["palabras"].set(f"{info['palabras']:,}")
        self.chips["urls"].set(str(info["urls"]))
        self.chips["adjuntos"].set(str(info["adjuntos"]))
        self.chips["formato"].set("HTML" if info["html"] else "Texto")

        resumen = info["cuerpo"][:3000] + ("\n…" if len(info["cuerpo"]) > 3000 else "")
        self.vista.configure(state="normal")
        self.vista.delete("1.0", "end")
        self.vista.insert("1.0", resumen or "(Sin contenido)")
        self.vista.configure(state="disabled")

        self._reiniciar_resultado()
        self.boton_clasificar.configure(state="normal")
        self.estado(f"Correo cargado: {Path(ruta).name}")

    def clasificar_correo(self):
        if not self.ruta_correo:
            return
        self.estado("Analizando correo…")
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        try:
            resultados = predecir(self.ruta_correo, RUTA_MODELO)
        except Exception as error:
            self.estado("Error al clasificar.")
            messagebox.showerror(
                "No se pudo clasificar",
                str(error),
                parent=self.root,
            )
            return
        finally:
            self.root.configure(cursor="")
            self.actualizar_modelo()

        _, etiqueta, confianza = resultados[0]
        spam = es_spam(etiqueta)
        self._mostrar_resultado(spam, confianza)

        self.total += 1
        self.total_spam += int(spam)
        self._actualizar_stats()

        fila = (datetime.now().strftime("%H:%M:%S"), Path(self.ruta_correo).name,
                self.info_correo["asunto"], "SPAM" if spam else "BUENO",
                f"{confianza * 100:.1f}%")
        self.historial.append(fila)
        self.tabla.insert("", 0, values=fila, tags=("spam" if spam else "ok",))
        self.estado(f"Resultado: {fila[3]} ({fila[4]}) — {fila[1]}")

    def limpiar_historial(self):
        self.historial.clear()
        self.tabla.delete(*self.tabla.get_children())
        self.total = self.total_spam = 0
        self._actualizar_stats()
        self.estado("Historial limpiado.")

    def exportar_csv(self):
        if not self.historial:
            messagebox.showinfo("Historial vacío", "Aún no hay resultados que exportar.",
                                parent=self.root)
            return
        ruta = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".csv", initialfile="resultados_spam.csv",
            filetypes=[("CSV", "*.csv")])
        if not ruta:
            return
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Hora", "Archivo", "Asunto", "Resultado", "Confianza"])
            w.writerows(self.historial)
        self.estado(f"Historial exportado a {ruta}")


def main():
    root = tk.Tk()
    SpamDetectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()