"""
IoT Signature Monitor
Surveillance et vérification de signatures pour flux MQTT.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import paho.mqtt.client as mqtt
import hmac, hashlib, base64, os, time, threading, socket, json
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw
import io
from pathlib import Path

# ============================================================
# Configuration
# ============================================================
SECRET_KEY = b"ma_cle_secrete_iot_2025"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_SUB = "iot/camera/#"
MQTT_TOPIC_PUB = "iot/camera/photo"

STOCKAGE = Path.home() / "Documents" / "IoT_Signature_Monitor"
PHOTOS_DIR = STOCKAGE / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
METADATA_FILE = STOCKAGE / "historique.json"

# Palette — thème sombre moderne
COLORS = {
    "fond":          "#0a0a18",
    "fond_clair":    "#141428",
    "carte":         "#1a1a2e",
    "carte_hover":   "#242440",
    "bordure":       "#2d2d4a",
    "primaire":      "#a78bfa",
    "primaire_fort": "#8b5cf6",
    "succes":        "#4ade80",
    "succes_fonce":  "#14532d",
    "danger":        "#f87171",
    "danger_fonce":  "#7f1d1d",
    "attention":     "#fbbf24",
    "texte":         "#e8e8f5",
    "texte_doux":    "#a8a8c8",
    "texte_faible":  "#6b6b8a",
}

# Couleurs du dégradé vertical du fond
DEGRADE_HAUT = (10, 10, 24)
DEGRADE_MILIEU = (20, 20, 45)
DEGRADE_BAS = (30, 20, 55)


# ============================================================
# Stockage persistant
# ============================================================
class Stockage:
    def __init__(self):
        self.historique = self._charger()

    def _charger(self):
        if METADATA_FILE.exists():
            try:
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _sauvegarder(self):
        try:
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.historique, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur sauvegarde : {e}")

    def ajouter(self, valide, taille, temps_us, image_b64, erreur=None):
        entree = {
            "horodatage": datetime.now().isoformat(),
            "valide": valide,
            "taille": taille,
            "temps_us": temps_us,
            "erreur": erreur,
            "photo": None,
        }
        if valide and image_b64:
            try:
                nom = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.jpg"
                chemin = PHOTOS_DIR / nom
                with open(chemin, "wb") as f:
                    f.write(base64.b64decode(image_b64))
                entree["photo"] = nom
            except Exception as e:
                print(f"Erreur image : {e}")
        self.historique.append(entree)
        self._sauvegarder()
        return entree

    def tout(self):
        return self.historique

    def vider(self):
        self.historique = []
        self._sauvegarder()

    def photos_valides(self):
        return [e for e in self.historique if e.get("photo")]

    def chemin_photo(self, entree):
        if entree.get("photo"):
            return PHOTOS_DIR / entree["photo"]
        return None


# ============================================================
# Application
# ============================================================
class IoTMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IoT Signature Monitor")
        self.root.geometry("1280x820")
        self.root.configure(bg=COLORS["fond"])
        self.root.minsize(1000, 640)

        self.stats = {"total": 0, "valides": 0, "rejetes": 0}
        self.stockage = Stockage()
        self.mqtt_client = None
        self.mqtt_connected = False
        self.derniere_entree = None
        self.degrade_ref = None

        for e in self.stockage.tout():
            self.stats["total"] += 1
            if e["valide"]:
                self.stats["valides"] += 1
            else:
                self.stats["rejetes"] += 1

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.ip_locale = s.getsockname()[0]
            s.close()
        except Exception:
            self.ip_locale = "127.0.0.1"

        # 1. Fond dégradé (placé en premier, reste en arrière-plan)
        self._creer_fond_degrade()

        # 2. Styles
        self._configurer_styles()

        # 3. Interface
        self._construire_entete()
        self._construire_onglets()
        self._construire_barre_etat()
        self._raccourcis()

        # 4. MQTT
        self._demarrer_mqtt()
        self._horloge()

    # --------------------------------------------------------
    # Fond dégradé
    # --------------------------------------------------------
    def _creer_fond_degrade(self):
        """Crée et affiche un fond dégradé vertical en arrière-plan."""
        largeur, hauteur = 1920, 1080
        img = Image.new("RGB", (largeur, hauteur))
        draw = ImageDraw.Draw(img)

        for y in range(hauteur):
            ratio = y / hauteur
            if ratio < 0.5:
                r1 = ratio * 2
                r = int(DEGRADE_HAUT[0] + (DEGRADE_MILIEU[0] - DEGRADE_HAUT[0]) * r1)
                g = int(DEGRADE_HAUT[1] + (DEGRADE_MILIEU[1] - DEGRADE_HAUT[1]) * r1)
                b = int(DEGRADE_HAUT[2] + (DEGRADE_MILIEU[2] - DEGRADE_HAUT[2]) * r1)
            else:
                r1 = (ratio - 0.5) * 2
                r = int(DEGRADE_MILIEU[0] + (DEGRADE_BAS[0] - DEGRADE_MILIEU[0]) * r1)
                g = int(DEGRADE_MILIEU[1] + (DEGRADE_BAS[1] - DEGRADE_MILIEU[1]) * r1)
                b = int(DEGRADE_MILIEU[2] + (DEGRADE_BAS[2] - DEGRADE_MILIEU[2]) * r1)
            draw.line([(0, y), (largeur, y)], fill=(r, g, b))

        self.degrade_ref = ImageTk.PhotoImage(img)
        self.label_fond = tk.Label(self.root, image=self.degrade_ref, bd=0)
        self.label_fond.place(x=0, y=0, relwidth=1, relheight=1)
        self.label_fond.lower()

    # --------------------------------------------------------
    # Styles
    # --------------------------------------------------------
    def _configurer_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TNotebook",
                        background=COLORS["fond"],
                        borderwidth=0,
                        tabmargins=[0, 0, 0, 0])

        style.configure("TNotebook.Tab",
                        background=COLORS["fond_clair"],
                        foreground=COLORS["texte_doux"],
                        padding=[22, 12],
                        font=("Segoe UI Semibold", 10),
                        borderwidth=0)

        style.map("TNotebook.Tab",
                  background=[("selected", COLORS["carte"])],
                  foreground=[("selected", COLORS["primaire"])])

        style.configure("Treeview",
                        background=COLORS["carte"],
                        foreground=COLORS["texte"],
                        fieldbackground=COLORS["carte"],
                        borderwidth=0,
                        font=("Segoe UI", 10),
                        rowheight=36)

        style.configure("Treeview.Heading",
                        background=COLORS["fond_clair"],
                        foreground=COLORS["texte_doux"],
                        font=("Segoe UI Semibold", 10),
                        borderwidth=0,
                        relief="flat")

        style.map("Treeview",
                  background=[("selected", COLORS["primaire"])],
                  foreground=[("selected", COLORS["fond"])])

    # --------------------------------------------------------
    # En-tête
    # --------------------------------------------------------
    def _construire_entete(self):
        entete = tk.Frame(self.root, bg=COLORS["fond"])
        entete.pack(fill="x", padx=28, pady=(20, 8))

        gauche = tk.Frame(entete, bg=COLORS["fond"])
        gauche.pack(side="left")

        tk.Label(gauche, text="IoT Signature Monitor",
                 bg=COLORS["fond"], fg=COLORS["primaire"],
                 font=("Segoe UI Semibold", 20)).pack(anchor="w")

        tk.Label(gauche, text="Surveillance et vérification de signatures en temps réel",
                 bg=COLORS["fond"], fg=COLORS["texte_faible"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        droite = tk.Frame(entete, bg=COLORS["fond"])
        droite.pack(side="right")

        self.indicateur = tk.Canvas(droite, width=14, height=14,
                                     bg=COLORS["fond"], highlightthickness=0)
        self.indicateur.pack()
        self.point = self.indicateur.create_oval(2, 2, 12, 12,
                                                  fill=COLORS["danger"], outline="")

    # --------------------------------------------------------
    # Onglets
    # --------------------------------------------------------
    def _construire_onglets(self):
        self.onglets = ttk.Notebook(self.root)
        self.onglets.pack(fill="both", expand=True, padx=24, pady=10)

        self.page_accueil = self._page_accueil()
        self.page_historique = self._page_historique()
        self.page_photos = self._page_photos()
        self.page_configuration = self._page_configuration()
        self.page_statistiques = self._page_statistiques()
        self.page_apropos = self._page_apropos()

        self.onglets.add(self.page_accueil, text="  Accueil  ")
        self.onglets.add(self.page_historique, text="  Historique  ")
        self.onglets.add(self.page_photos, text="  Photos  ")
        self.onglets.add(self.page_configuration, text="  Configuration  ")
        self.onglets.add(self.page_statistiques, text="  Statistiques  ")
        self.onglets.add(self.page_apropos, text="  À propos  ")

    # --------------------------------------------------------
    # Page Accueil
    # --------------------------------------------------------
    def _page_accueil(self):
        page = tk.Frame(self.onglets, bg=COLORS["fond"])

        conteneur = tk.Frame(page, bg=COLORS["fond"])
        conteneur.pack(fill="both", expand=True, padx=20, pady=20)

        cartes = tk.Frame(conteneur, bg=COLORS["fond"])
        cartes.pack(fill="x", pady=(0, 20))
        for i in range(4):
            cartes.columnconfigure(i, weight=1, uniform="carte")

        self.carte_total = self._carte_stat(cartes, "Messages reçus",
                                             "0", COLORS["primaire"])
        self.carte_valides = self._carte_stat(cartes, "Signatures valides",
                                               "0", COLORS["succes"])
        self.carte_rejetes = self._carte_stat(cartes, "Messages rejetés",
                                               "0", COLORS["danger"])
        self.carte_taux = self._carte_stat(cartes, "Taux de validité",
                                            "0%", COLORS["attention"])

        self.carte_total.grid(row=0, column=0, sticky="nsew", padx=6)
        self.carte_valides.grid(row=0, column=1, sticky="nsew", padx=6)
        self.carte_rejetes.grid(row=0, column=2, sticky="nsew", padx=6)
        self.carte_taux.grid(row=0, column=3, sticky="nsew", padx=6)

        bandeau = tk.Frame(conteneur, bg=COLORS["carte"],
                           highlightbackground=COLORS["bordure"],
                           highlightthickness=1)
        bandeau.pack(fill="x", pady=(0, 20))

        tk.Label(bandeau, text="Bienvenue",
                 bg=COLORS["carte"], fg=COLORS["primaire"],
                 font=("Segoe UI Semibold", 14)).pack(anchor="w",
                                                       padx=20, pady=(16, 4))

        tk.Label(bandeau,
                 text="Cette application surveille les messages MQTT publiés par vos objets "
                      "connectés, vérifie leur signature et conserve chaque image reçue. "
                      "Vous pouvez consulter l'historique complet et parcourir les photos "
                      "enregistrées à tout moment.",
                 bg=COLORS["carte"], fg=COLORS["texte_doux"],
                 font=("Segoe UI", 10), justify="left",
                 wraplength=1000).pack(anchor="w", padx=20, pady=(0, 16))

        tk.Label(conteneur, text="Actions rapides",
                 bg=COLORS["fond"], fg=COLORS["texte"],
                 font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 10))

        actions = tk.Frame(conteneur, bg=COLORS["fond"])
        actions.pack(fill="x")

        self._bouton(actions, "Voir l'historique",
                     lambda: self.onglets.select(1),
                     COLORS["fond_clair"]).pack(side="left", padx=(0, 8))
        self._bouton(actions, "Parcourir les photos",
                     lambda: self.onglets.select(2),
                     COLORS["fond_clair"]).pack(side="left", padx=(0, 8))
        self._bouton(actions, "Envoyer un message valide",
                     self._simuler_valide,
                     COLORS["succes"]).pack(side="left", padx=(0, 8))
        self._bouton(actions, "Simuler un attaquant",
                     self._simuler_attaque,
                     COLORS["danger"]).pack(side="left", padx=(0, 8))

        return page

    def _carte_stat(self, parent, titre, valeur, couleur):
        cadre = tk.Frame(parent, bg=COLORS["carte"],
                         highlightbackground=COLORS["bordure"],
                         highlightthickness=1)
        cadre.configure(padx=20, pady=18)

        tk.Label(cadre, text=titre.upper(),
                 bg=COLORS["carte"], fg=COLORS["texte_faible"],
                 font=("Segoe UI Semibold", 8)).pack(anchor="w")

        label_valeur = tk.Label(cadre, text=valeur,
                                 bg=COLORS["carte"], fg=couleur,
                                 font=("Segoe UI Semibold", 26))
        label_valeur.pack(anchor="w", pady=(6, 0))
        cadre.label_valeur = label_valeur
        return cadre

    def _bouton(self, parent, texte, commande, couleur_fond):
        couleur_texte = "white" if couleur_fond in (COLORS["succes"],
                                                     COLORS["danger"]) else COLORS["texte"]
        b = tk.Button(parent, text=texte, command=commande,
                      bg=couleur_fond, fg=couleur_texte,
                      activebackground=COLORS["primaire"],
                      activeforeground=COLORS["fond"],
                      relief="flat", cursor="hand2", bd=0,
                      font=("Segoe UI Semibold", 10),
                      padx=18, pady=10)
        b.bind("<Enter>", lambda e: b.config(bg=COLORS["carte_hover"]))
        b.bind("<Leave>", lambda e: b.config(bg=couleur_fond))
        return b

    # --------------------------------------------------------
    # Page Historique
    # --------------------------------------------------------
    def _page_historique(self):
        page = tk.Frame(self.onglets, bg=COLORS["fond"])

        conteneur = tk.Frame(page, bg=COLORS["fond"])
        conteneur.pack(fill="both", expand=True, padx=20, pady=20)
        conteneur.columnconfigure(0, weight=3)
        conteneur.columnconfigure(1, weight=2)
        conteneur.rowconfigure(1, weight=1)

        barre = tk.Frame(conteneur, bg=COLORS["fond"])
        barre.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        tk.Label(barre, text="Historique des messages",
                 bg=COLORS["fond"], fg=COLORS["texte"],
                 font=("Segoe UI Semibold", 13)).pack(side="left")

        self.compteur_hist = tk.Label(barre, text="0 message",
                                       bg=COLORS["fond"], fg=COLORS["texte_faible"],
                                       font=("Segoe UI", 9, "italic"))
        self.compteur_hist.pack(side="left", padx=12)

        self._bouton(barre, "Effacer l'historique", self._effacer_historique,
                     COLORS["fond_clair"]).pack(side="right", padx=(6, 0))
        self._bouton(barre, "Exporter", self._exporter,
                     COLORS["fond_clair"]).pack(side="right")

        cadre_tableau = tk.Frame(conteneur, bg=COLORS["carte"],
                                 highlightbackground=COLORS["bordure"],
                                 highlightthickness=1)
        cadre_tableau.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        colonnes = ("horodatage", "statut", "taille", "temps")
        self.tableau = ttk.Treeview(cadre_tableau, columns=colonnes,
                                     show="headings", height=20)
        self.tableau.heading("horodatage", text="Horodatage")
        self.tableau.heading("statut", text="Statut")
        self.tableau.heading("taille", text="Taille (octets)")
        self.tableau.heading("temps", text="Temps HMAC (µs)")

        self.tableau.column("horodatage", width=160, anchor="center")
        self.tableau.column("statut", width=140, anchor="center")
        self.tableau.column("taille", width=130, anchor="center")
        self.tableau.column("temps", width=140, anchor="center")

        self.tableau.tag_configure("valide",
                                    background=COLORS["succes_fonce"],
                                    foreground="#bbf7d0")
        self.tableau.tag_configure("rejete",
                                    background=COLORS["danger_fonce"],
                                    foreground="#fecaca")

        scroll = ttk.Scrollbar(cadre_tableau, orient="vertical",
                                command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=scroll.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.tableau.bind("<<TreeviewSelect>>", self._selection_historique)
        self.tableau.bind("<Button-3>", self._menu_contextuel)

        self.menu_ctx = tk.Menu(self.tableau, tearoff=0)
        self.menu_ctx.add_command(label="Ouvrir la photo",
                                   command=self._ouvrir_photo_selection)
        self.menu_ctx.add_command(label="Copier la ligne",
                                   command=self._copier_ligne)

        cadre_apercu = tk.Frame(conteneur, bg=COLORS["carte"],
                                highlightbackground=COLORS["bordure"],
                                highlightthickness=1)
        cadre_apercu.grid(row=1, column=1, sticky="nsew")

        tk.Label(cadre_apercu, text="Aperçu",
                 bg=COLORS["carte"], fg=COLORS["texte"],
                 font=("Segoe UI Semibold", 12)).pack(anchor="w",
                                                       padx=16, pady=(14, 8))

        self.zone_image = tk.Frame(cadre_apercu, bg=COLORS["fond_clair"],
                                    width=320, height=280,
                                    highlightbackground=COLORS["bordure"],
                                    highlightthickness=1)
        self.zone_image.pack(padx=16, pady=6)
        self.zone_image.pack_propagate(False)

        self.label_image = tk.Label(self.zone_image,
                                     text="Aucune image\nsélectionnée",
                                     bg=COLORS["fond_clair"],
                                     fg=COLORS["texte_faible"],
                                     font=("Segoe UI", 10))
        self.label_image.pack(expand=True)

        self.info_image = tk.Label(cadre_apercu, text="",
                                    bg=COLORS["carte"], fg=COLORS["texte_doux"],
                                    font=("Segoe UI", 9), justify="left")
        self.info_image.pack(anchor="w", padx=16, pady=8)

        self._bouton(cadre_apercu, "Ouvrir la photo sélectionnée",
                     self._ouvrir_photo_selection,
                     COLORS["fond_clair"]).pack(fill="x", padx=16, pady=(4, 16))

        self._recharger_tableau()
        return page

    def _recharger_tableau(self):
        for item in self.tableau.get_children():
            self.tableau.delete(item)

        entrees = self.stockage.tout()
        for e in reversed(entrees):
            horodatage = datetime.fromisoformat(e["horodatage"]).strftime("%d/%m %H:%M:%S")
            statut = "VALIDE" if e["valide"] else "REJETÉ"
            tag = "valide" if e["valide"] else "rejete"
            taille = e["taille"]
            temps = f"{e['temps_us']:.1f}" if e["valide"] else "—"

            self.tableau.insert("", "end",
                                values=(horodatage, statut, taille, temps),
                                tags=(tag,))

        self.compteur_hist.config(text=f"{len(entrees)} message(s)")

        # Sélection automatique de la dernière photo
        self._selectionner_derniere_photo(entrees)

    def _selectionner_derniere_photo(self, entrees):
        """Affiche automatiquement l'aperçu de la dernière photo reçue."""
        entrees_inversees = list(reversed(entrees))
        children = self.tableau.get_children()

        for i, child in enumerate(children):
            if i >= len(entrees_inversees):
                break
            e = entrees_inversees[i]
            if e.get("photo"):
                self.tableau.selection_set(child)
                self.tableau.focus(child)
                self.tableau.see(child)
                self._selection_historique()
                return

        # Aucune photo : on vide l'aperçu
        self.label_image.config(image="", text="Aucune image\nsélectionnée")
        self.info_image.config(text="")
        self.derniere_entree = None

    def _selection_historique(self, event=None):
        sel = self.tableau.selection()
        if not sel:
            return

        index = self.tableau.index(sel[0])
        entrees = list(reversed(self.stockage.tout()))
        if index >= len(entrees):
            return

        e = entrees[index]
        self.derniere_entree = e

        chemin = self.stockage.chemin_photo(e)
        if chemin and chemin.exists():
            try:
                img = Image.open(chemin)
                img.thumbnail((300, 260), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.label_image.config(image=photo, text="")
                self.label_image.image = photo
                self.info_image.config(
                    text=f"Taille : {e['taille']} octets\n"
                         f"Temps de vérification : {e['temps_us']:.1f} µs\n"
                         f"Date : {datetime.fromisoformat(e['horodatage']).strftime('%d/%m/%Y %H:%M:%S')}")
            except Exception as err:
                self.label_image.config(image="", text=f"Erreur : {err}")
                self.info_image.config(text="")
        else:
            self.label_image.config(image="", text="Message sans image")
            self.info_image.config(text=f"Statut : REJETÉ\n"
                                         f"Raison : {e.get('erreur') or 'signature invalide'}")

    def _ouvrir_photo_selection(self):
        if not self.derniere_entree:
            return
        chemin = self.stockage.chemin_photo(self.derniere_entree)
        if chemin and chemin.exists():
            try:
                os.startfile(chemin)
            except Exception:
                messagebox.showinfo("Photo", f"Fichier : {chemin}")

    def _copier_ligne(self):
        sel = self.tableau.selection()
        if not sel:
            return
        vals = self.tableau.item(sel[0])["values"]
        self.root.clipboard_clear()
        self.root.clipboard_append("\t".join(str(v) for v in vals))

    def _menu_contextuel(self, event):
        try:
            self.menu_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_ctx.grab_release()

    # --------------------------------------------------------
    # Page Photos
    # --------------------------------------------------------
    def _page_photos(self):
        page = tk.Frame(self.onglets, bg=COLORS["fond"])

        conteneur = tk.Frame(page, bg=COLORS["fond"])
        conteneur.pack(fill="both", expand=True, padx=20, pady=20)

        barre = tk.Frame(conteneur, bg=COLORS["fond"])
        barre.pack(fill="x", pady=(0, 12))

        tk.Label(barre, text="Photos enregistrées",
                 bg=COLORS["fond"], fg=COLORS["texte"],
                 font=("Segoe UI Semibold", 13)).pack(side="left")

        self.compteur_photos = tk.Label(barre, text="0 photo",
                                         bg=COLORS["fond"], fg=COLORS["texte_faible"],
                                         font=("Segoe UI", 9, "italic"))
        self.compteur_photos.pack(side="left", padx=12)

        self._bouton(barre, "Ouvrir le dossier de stockage",
                     self._ouvrir_dossier_photos,
                     COLORS["fond_clair"]).pack(side="right")

        cadre_scroll = tk.Frame(conteneur, bg=COLORS["fond"])
        cadre_scroll.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(cadre_scroll, bg=COLORS["fond"],
                                 highlightthickness=0)
        scrollbar = ttk.Scrollbar(cadre_scroll, orient="vertical",
                                    command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.cadre_photos = tk.Frame(self.canvas, bg=COLORS["fond"])
        self.canvas.create_window((0, 0), window=self.cadre_photos, anchor="nw")

        self.cadre_photos.bind("<Configure>",
                                lambda e: self.canvas.configure(
                                    scrollregion=self.canvas.bbox("all")))

        self.canvas.bind_all("<MouseWheel>",
                              lambda e: self.canvas.yview_scroll(
                                  int(-1 * (e.delta / 120)), "units"))

        self._recharger_photos()
        return page

    def _recharger_photos(self):
        for w in self.cadre_photos.winfo_children():
            w.destroy()

        entrees = [e for e in self.stockage.tout() if e.get("photo")]
        self.compteur_photos.config(text=f"{len(entrees)} photo(s)")

        if not entrees:
            tk.Label(self.cadre_photos,
                     text="Aucune photo enregistrée pour le moment.\n"
                          "Les images reçues apparaîtront ici automatiquement.",
                     bg=COLORS["fond"], fg=COLORS["texte_faible"],
                     font=("Segoe UI", 10), justify="center").pack(pady=80)
            return

        colonnes = 4
        for i in range(colonnes):
            self.cadre_photos.columnconfigure(i, weight=1)

        for i, e in enumerate(reversed(entrees)):
            chemin = self.stockage.chemin_photo(e)
            if not chemin or not chemin.exists():
                continue

            ligne = i // colonnes
            colonne = i % colonnes

            carte = tk.Frame(self.cadre_photos, bg=COLORS["carte"],
                             highlightbackground=COLORS["bordure"],
                             highlightthickness=1)
            carte.grid(row=ligne, column=colonne, padx=8, pady=8, sticky="nsew")

            try:
                img = Image.open(chemin)
                img.thumbnail((200, 150), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)

                label_img = tk.Label(carte, image=photo, bg=COLORS["carte"],
                                      cursor="hand2")
                label_img.image = photo
                label_img.pack(padx=10, pady=(10, 4))
                label_img.bind("<Button-1>",
                                lambda ev, c=chemin: os.startfile(c))
            except Exception:
                tk.Label(carte, text="Erreur", bg=COLORS["carte"],
                         fg=COLORS["danger"]).pack(padx=10, pady=10)

            horodatage = datetime.fromisoformat(e["horodatage"]).strftime("%d/%m %H:%M")
            tk.Label(carte, text=horodatage, bg=COLORS["carte"],
                     fg=COLORS["texte_doux"], font=("Segoe UI", 8)).pack(pady=(0, 8))

    def _ouvrir_dossier_photos(self):
        try:
            os.startfile(PHOTOS_DIR)
        except Exception:
            messagebox.showinfo("Dossier", str(PHOTOS_DIR))

    # --------------------------------------------------------
    # Page Configuration
    # --------------------------------------------------------
    def _page_configuration(self):
        page = tk.Frame(self.onglets, bg=COLORS["fond"])

        conteneur = tk.Frame(page, bg=COLORS["fond"])
        conteneur.pack(fill="both", expand=True, padx=30, pady=30)

        tk.Label(conteneur, text="Configuration de la communication",
                 bg=COLORS["fond"], fg=COLORS["texte"],
                 font=("Segoe UI Semibold", 16)).pack(anchor="w")

        tk.Label(conteneur,
                 text="Ces informations doivent être renseignées dans le programme "
                      "embarqué de l'objet connecté.",
                 bg=COLORS["fond"], fg=COLORS["texte_faible"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 20))

        bloc1 = tk.Frame(conteneur, bg=COLORS["carte"],
                         highlightbackground=COLORS["bordure"],
                         highlightthickness=1)
        bloc1.pack(fill="x", pady=8)

        tk.Label(bloc1, text="Serveur de messages",
                 bg=COLORS["carte"], fg=COLORS["primaire"],
                 font=("Segoe UI Semibold", 12)).pack(anchor="w",
                                                       padx=20, pady=(16, 6))

        for libelle, valeur in [
            ("Adresse du serveur", self.ip_locale),
            ("Port", str(MQTT_PORT)),
            ("Sujet d'écoute", MQTT_TOPIC_SUB),
            ("Sujet de publication", MQTT_TOPIC_PUB),
        ]:
            ligne = tk.Frame(bloc1, bg=COLORS["carte"])
            ligne.pack(fill="x", padx=20, pady=3)
            tk.Label(ligne, text=libelle, bg=COLORS["carte"],
                     fg=COLORS["texte_doux"], font=("Segoe UI", 10),
                     width=24, anchor="w").pack(side="left")
            tk.Label(ligne, text=valeur, bg=COLORS["carte"],
                     fg=COLORS["texte"], font=("Consolas", 11)).pack(side="left")
        tk.Label(bloc1, text="", bg=COLORS["carte"]).pack(pady=6)

        bloc2 = tk.Frame(conteneur, bg=COLORS["carte"],
                         highlightbackground=COLORS["bordure"],
                         highlightthickness=1)
        bloc2.pack(fill="x", pady=8)

        tk.Label(bloc2, text="Sécurité",
                 bg=COLORS["carte"], fg=COLORS["succes"],
                 font=("Segoe UI Semibold", 12)).pack(anchor="w",
                                                       padx=20, pady=(16, 6))

        for libelle, valeur in [
            ("Algorithme de signature", "HMAC-SHA256"),
            ("Fonctions bas niveau", "xor_cipher, secure_memcmp"),
            ("Stockage des photos", str(PHOTOS_DIR)),
            ("Fichier d'historique", str(METADATA_FILE)),
        ]:
            ligne = tk.Frame(bloc2, bg=COLORS["carte"])
            ligne.pack(fill="x", padx=20, pady=3)
            tk.Label(ligne, text=libelle, bg=COLORS["carte"],
                     fg=COLORS["texte_doux"], font=("Segoe UI", 10),
                     width=24, anchor="w").pack(side="left")
            tk.Label(ligne, text=valeur, bg=COLORS["carte"],
                     fg=COLORS["texte"], font=("Consolas", 10),
                     wraplength=600, justify="left").pack(side="left")
        tk.Label(bloc2, text="", bg=COLORS["carte"]).pack(pady=6)

        self._bouton(conteneur, "Copier la configuration",
                     self._copier_config,
                     COLORS["primaire_fort"]).pack(pady=20)

        return page

    def _copier_config(self):
        texte = (
            f"Wi-Fi : kkkk / 12345678\n"
            f"Serveur : {self.ip_locale}:{MQTT_PORT}\n"
            f"Sujet : {MQTT_TOPIC_PUB}\n"
            f"Clé secrète : ma_cle_secrete_iot_2025"
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(texte)
        self._status("Configuration copiée dans le presse-papiers")

    # --------------------------------------------------------
    # Page Statistiques
    # --------------------------------------------------------
    def _page_statistiques(self):
        page = tk.Frame(self.onglets, bg=COLORS["fond"])

        conteneur = tk.Frame(page, bg=COLORS["fond"])
        conteneur.pack(fill="both", expand=True, padx=30, pady=30)

        tk.Label(conteneur, text="Statistiques d'activité",
                 bg=COLORS["fond"], fg=COLORS["texte"],
                 font=("Segoe UI Semibold", 16)).pack(anchor="w", pady=(0, 20))

        cartes = tk.Frame(conteneur, bg=COLORS["fond"])
        cartes.pack(fill="x")
        for i in range(4):
            cartes.columnconfigure(i, weight=1, uniform="stat")

        self.stat_total = self._carte_info(cartes, "Total", "0", COLORS["primaire"])
        self.stat_valides = self._carte_info(cartes, "Valides", "0", COLORS["succes"])
        self.stat_rejetes = self._carte_info(cartes, "Rejetés", "0", COLORS["danger"])
        self.stat_photos = self._carte_info(cartes, "Photos", "0", COLORS["attention"])

        self.stat_total.grid(row=0, column=0, sticky="nsew", padx=6)
        self.stat_valides.grid(row=0, column=1, sticky="nsew", padx=6)
        self.stat_rejetes.grid(row=0, column=2, sticky="nsew", padx=6)
        self.stat_photos.grid(row=0, column=3, sticky="nsew", padx=6)

        tk.Label(conteneur, text="Journal d'activité",
                 bg=COLORS["fond"], fg=COLORS["texte"],
                 font=("Segoe UI Semibold", 12)).pack(anchor="w",
                                                       pady=(30, 10))

        cadre_log = tk.Frame(conteneur, bg=COLORS["carte"],
                             highlightbackground=COLORS["bordure"],
                             highlightthickness=1)
        cadre_log.pack(fill="both", expand=True)

        self.journal = tk.Text(cadre_log, bg=COLORS["carte"],
                                fg=COLORS["texte"], relief="flat",
                                font=("Consolas", 10), height=14,
                                insertbackground=COLORS["primaire"])
        self.journal.pack(fill="both", expand=True, padx=12, pady=12)
        self.journal.config(state="disabled")

        self._maj_stats()
        return page

    def _carte_info(self, parent, titre, valeur, couleur):
        cadre = tk.Frame(parent, bg=COLORS["carte"],
                         highlightbackground=COLORS["bordure"],
                         highlightthickness=1)
        cadre.configure(padx=20, pady=16)

        tk.Label(cadre, text=titre.upper(),
                 bg=COLORS["carte"], fg=COLORS["texte_faible"],
                 font=("Segoe UI Semibold", 8)).pack(anchor="w")
        label = tk.Label(cadre, text=valeur,
                          bg=COLORS["carte"], fg=couleur,
                          font=("Segoe UI Semibold", 22))
        label.pack(anchor="w", pady=(4, 0))
        cadre.label_valeur = label
        return cadre

    def _maj_stats(self):
        self.carte_total.label_valeur.config(text=str(self.stats["total"]))
        self.carte_valides.label_valeur.config(text=str(self.stats["valides"]))
        self.carte_rejetes.label_valeur.config(text=str(self.stats["rejetes"]))

        total = self.stats["total"]
        taux = (self.stats["valides"] / total * 100) if total else 0
        self.carte_taux.label_valeur.config(text=f"{taux:.0f}%")

        self.stat_total.label_valeur.config(text=str(total))
        self.stat_valides.label_valeur.config(text=str(self.stats["valides"]))
        self.stat_rejetes.label_valeur.config(text=str(self.stats["rejetes"]))
        self.stat_photos.label_valeur.config(
            text=str(len(self.stockage.photos_valides())))

    # --------------------------------------------------------
    # Page À propos
    # --------------------------------------------------------
    def _page_apropos(self):
        page = tk.Frame(self.onglets, bg=COLORS["fond"])

        conteneur = tk.Frame(page, bg=COLORS["fond"])
        conteneur.pack(fill="both", expand=True, padx=40, pady=40)

        carte = tk.Frame(conteneur, bg=COLORS["carte"],
                         highlightbackground=COLORS["bordure"],
                         highlightthickness=1)
        carte.pack(fill="both", expand=True)

        tk.Label(carte, text="🔐",
                 bg=COLORS["carte"], fg=COLORS["primaire"],
                 font=("Segoe UI", 56)).pack(pady=(40, 10))

        tk.Label(carte, text="IoT Signature Monitor",
                 bg=COLORS["carte"], fg=COLORS["texte"],
                 font=("Segoe UI Semibold", 22)).pack()

        tk.Label(carte, text="Version 2.0",
                 bg=COLORS["carte"], fg=COLORS["texte_faible"],
                 font=("Segoe UI", 10)).pack(pady=(2, 30))

        texte = (
            "Cette application a été conçue pour surveiller et vérifier en temps réel "
            "les messages échangés entre des objets connectés et un serveur. Elle "
            "s'inscrit dans une démarche de sécurisation des communications dans "
            "l'Internet des objets, où les ressources matérielles sont limitées.\n\n"
            "Le principe est simple : chaque message est accompagné d'une signature "
            "calculée à partir d'une clé secrète partagée. L'application recalcule "
            "cette signature à la réception, la compare, puis décide d'accepter ou "
            "de rejeter le message. Toute altération, même d'un seul octet, rend la "
            "signature invalide et le message est immédiatement écarté.\n\n"
            "Les traitements critiques — chiffrement et comparaison sécurisée — ont "
            "été implémentés en assembleur natif, directement au plus près du "
            "processeur, afin de réduire au minimum le temps de calcul et la "
            "consommation d'énergie.\n\n"
            "Chaque image reçue est automatiquement archivée sur le disque, "
            "accompagnée de son horodatage, ce qui permet de conserver une trace "
            "consultable de toutes les communications validées."
        )

        tk.Label(carte, text=texte,
                 bg=COLORS["carte"], fg=COLORS["texte_doux"],
                 font=("Segoe UI", 10), justify="left",
                 wraplength=800).pack(padx=40, pady=10)

        pied = tk.Frame(carte, bg=COLORS["carte"])
        pied.pack(fill="x", pady=(20, 30))

        tk.Label(pied, text="Réalisé dans le cadre d'un projet académique",
                 bg=COLORS["carte"], fg=COLORS["texte_faible"],
                 font=("Segoe UI", 9, "italic")).pack()

        tk.Label(pied, text="Année universitaire 2025 – 2026",
                 bg=COLORS["carte"], fg=COLORS["texte_faible"],
                 font=("Segoe UI", 9)).pack(pady=(4, 0))

        return page

    # --------------------------------------------------------
    # Barre d'état
    # --------------------------------------------------------
    def _construire_barre_etat(self):
        barre = tk.Frame(self.root, bg=COLORS["fond_clair"], height=30)
        barre.pack(fill="x", side="bottom")
        barre.pack_propagate(False)

        self.texte_status = tk.Label(barre,
                                      text="Connexion en cours...",
                                      bg=COLORS["fond_clair"],
                                      fg=COLORS["texte_doux"],
                                      font=("Segoe UI", 9), anchor="w")
        self.texte_status.pack(side="left", padx=20)

        self.label_heure = tk.Label(barre, text="",
                                     bg=COLORS["fond_clair"],
                                     fg=COLORS["texte_faible"],
                                     font=("Segoe UI", 9))
        self.label_heure.pack(side="right", padx=20)

    # --------------------------------------------------------
    # Raccourcis
    # --------------------------------------------------------
    def _raccourcis(self):
        self.root.bind("<Control-q>", lambda e: self._quitter())
        self.root.bind("<Control-e>", lambda e: self._exporter())
        self.root.bind("<F5>", lambda e: self._recharger_photos())
        for i in range(6):
            self.root.bind(f"<Control-Key-{i+1}>",
                            lambda e, n=i: self.onglets.select(n))

    # --------------------------------------------------------
    # Horloge
    # --------------------------------------------------------
    def _horloge(self):
        self.label_heure.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._horloge)

    # --------------------------------------------------------
    # MQTT
    # --------------------------------------------------------
    def _demarrer_mqtt(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_disconnect = self._on_disconnect

        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            threading.Thread(target=self.mqtt_client.loop_forever,
                              daemon=True).start()
        except Exception as e:
            self._status(f"Connexion impossible : {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.mqtt_connected = True
            client.subscribe(MQTT_TOPIC_SUB)
            self.root.after(0, self._maj_indicateur, True)
            self.root.after(0, self._status,
                            f"Connecté — écoute sur {MQTT_TOPIC_SUB}")
        else:
            self.root.after(0, self._status, f"Échec de connexion (code {rc})")

    def _on_disconnect(self, client, userdata, rc):
        self.mqtt_connected = False
        self.root.after(0, self._maj_indicateur, False)
        self.root.after(0, self._status, "Déconnecté")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            if "|" not in payload:
                self.root.after(0, self._traiter_message,
                                False, len(msg.payload), 0, None, "Sans signature")
                return

            image_b64, signature_hex = payload.split("|", 1)
            sig_recue = bytes.fromhex(signature_hex)

            t0 = time.perf_counter()
            sig_calc = hmac.new(SECRET_KEY, image_b64.encode(),
                                 hashlib.sha256).digest()
            t1 = time.perf_counter()
            valide = hmac.compare_digest(sig_calc, sig_recue)
            temps_us = (t1 - t0) * 1e6

            self.root.after(0, self._traiter_message,
                            valide, len(msg.payload), temps_us,
                            image_b64 if valide else None, None)
        except Exception as e:
            self.root.after(0, self._traiter_message,
                            False, len(msg.payload), 0, None, str(e))

    def _maj_indicateur(self, connecte):
        couleur = COLORS["succes"] if connecte else COLORS["danger"]
        self.indicateur.itemconfig(self.point, fill=couleur)

    def _status(self, texte):
        self.texte_status.config(text=texte)

    # --------------------------------------------------------
    # Traitement d'un message
    # --------------------------------------------------------
    def _traiter_message(self, valide, taille, temps_us, image_b64, erreur):
        self.stockage.ajouter(valide, taille, temps_us, image_b64, erreur)

        self.stats["total"] += 1
        if valide:
            self.stats["valides"] += 1
        else:
            self.stats["rejetes"] += 1

        self._maj_stats()
        self._recharger_tableau()
        self._recharger_photos()

        horodatage = datetime.now().strftime("%H:%M:%S")
        if valide:
            self._status(f"Message valide reçu à {horodatage} — {temps_us:.1f} µs")
            self._journal(f"[{horodatage}] valide — {taille} octets — {temps_us:.1f} µs")
        else:
            self._status(f"Message rejeté à {horodatage}")
            self._journal(f"[{horodatage}] rejeté — {taille} octets — {erreur or 'signature invalide'}")

    def _journal(self, ligne):
        self.journal.config(state="normal")
        self.journal.insert("end", ligne + "\n")
        self.journal.see("end")
        self.journal.config(state="disabled")

    # --------------------------------------------------------
    # Actions
    # --------------------------------------------------------
    def _effacer_historique(self):
        if not messagebox.askyesno("Confirmation",
                                    "Effacer tout l'historique ?\n"
                                    "Les photos enregistrées sur le disque ne seront pas supprimées."):
            return
        self.stockage.vider()
        self.stats = {"total": 0, "valides": 0, "rejetes": 0}
        self._maj_stats()
        self._recharger_tableau()
        self.label_image.config(image="", text="Aucune image\nsélectionnée")
        self.info_image.config(text="")
        self._status("Historique effacé")

    def _exporter(self):
        chemin = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"historique_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        if not chemin:
            return
        try:
            import csv
            with open(chemin, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Horodatage", "Statut", "Taille", "Temps_us", "Photo"])
                for e in self.stockage.tout():
                    writer.writerow([
                        e["horodatage"],
                        "VALIDE" if e["valide"] else "REJETÉ",
                        e["taille"],
                        f"{e['temps_us']:.2f}",
                        e.get("photo") or ""
                    ])
            messagebox.showinfo("Export", f"Historique exporté :\n{chemin}")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _simuler_valide(self):
        def envoyer():
            try:
                image_b64 = base64.b64encode(b"IMAGE_DE_TEST").decode()
                sig = hmac.new(SECRET_KEY, image_b64.encode(),
                               hashlib.sha256).hexdigest()
                c = mqtt.Client()
                c.connect(MQTT_BROKER, MQTT_PORT, 60)
                c.publish(MQTT_TOPIC_PUB, f"{image_b64}|{sig}")
                c.disconnect()
            except Exception as e:
                self.root.after(0, self._status, f"Erreur : {e}")
        threading.Thread(target=envoyer, daemon=True).start()
        self._status("Envoi d'un message valide...")

    def _simuler_attaque(self):
        def envoyer():
            try:
                image_b64 = base64.b64encode(b"FAUSSE_IMAGE").decode()
                sig = "00" * 32
                c = mqtt.Client()
                c.connect(MQTT_BROKER, MQTT_PORT, 60)
                c.publish(MQTT_TOPIC_PUB, f"{image_b64}|{sig}")
                c.disconnect()
            except Exception as e:
                self.root.after(0, self._status, f"Erreur : {e}")
        threading.Thread(target=envoyer, daemon=True).start()
        self._status("Simulation d'un attaquant...")

    def _quitter(self):
        if messagebox.askyesno("Quitter", "Fermer l'application ?"):
            try:
                self.mqtt_client.disconnect()
            except Exception:
                pass
            self.root.quit()
            self.root.destroy()


# ============================================================
# Lancement
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = IoTMonitorApp(root)
    root.mainloop()