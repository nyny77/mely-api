"""
Widget de gestion du module Visio Familles
Permet de gérer les résidents, familles, rendez-vous et lancer des appels vidéo
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QTabWidget, QLineEdit, QTextEdit, QDateTimeEdit,
                               QComboBox, QMessageBox, QHeaderView, QFrame)
from PySide6.QtCore import Qt, Signal, QDateTime, QTimer
from PySide6.QtGui import QFont, QKeyEvent
from datetime import datetime, timedelta, timezone
import webbrowser
import hashlib
import os

from core.database import SessionLocal
from core.models import Resident, Famille, RendezVous, Animatrice
from core.widgets.visio_dialogs import AddResidentDialog, AddFamilleDialog
from core.widgets.email_config_dialog import EmailConfigDialog
from core.widgets.visio_stats import VisioStatsWidget
from core.email_service import email_service


class VisioWidget(QWidget):
    """Widget principal du module Visio Familles"""
    back_requested = Signal()
    
    def __init__(self):
        super().__init__()
        self.current_focus_index = 0  # Index du widget ayant le focus
        self.focusable_widgets = []  # Liste des widgets navigables
        self.setup_ui()
        self.load_data()
        self.setup_focus_navigation()
        self.setup_auto_refresh()
        
        # Réafficher le curseur de la souris pour ce module
        self.show_cursor()
    
    def show_cursor(self):
        """Réaffiche le curseur de la souris pour le module Visio"""
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QApplication
        # Forcer le curseur sur toute l'application quand on est dans Visio
        QApplication.setOverrideCursor(QCursor(Qt.ArrowCursor))
        print("🖱️ Curseur de souris réactivé pour le module Visio")
    
    def hide_cursor(self):
        """Cache le curseur quand on quitte le module Visio"""
        from PySide6.QtWidgets import QApplication
        # Restaurer le curseur caché de Mely
        QApplication.restoreOverrideCursor()
        print("🖱️ Curseur de souris caché (retour à Mely)")
    
    def showEvent(self, event):
        """Appelé quand le widget devient visible"""
        super().showEvent(event)
        self.show_cursor()
    
    def hideEvent(self, event):
        """Appelé quand le widget est caché"""
        super().hideEvent(event)
        self.hide_cursor()
    
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Titre
        title = QLabel("📹 VISIO FAMILLES")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-family: 'Poetsen One', sans-serif;
                font-size: 48px;
                color: #9146ff;
                font-weight: bold;
                margin-bottom: 20px;
            }
        """)
        main_layout.addWidget(title)
        
        # Onglets
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #9146ff;
                border-radius: 10px;
                background-color: #1a1a2e;
            }
            QTabBar::tab {
                background-color: #2a2a3e;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 16px;
                padding: 10px 20px;
                margin: 2px;
                border-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: #9146ff;
            }
        """)
        
        # Créer les onglets
        self.tab_inscriptions = self.create_inscriptions_tab()
        self.tab_demandes = self.create_demandes_tab()
        self.tab_planning = self.create_planning_tab()
        self.tab_residents = self.create_residents_tab()
        self.tab_familles = self.create_familles_tab()
        
        self.tabs.addTab(self.tab_inscriptions, "📋 Inscriptions")
        self.inscriptions_tab_index = 0
        self.tabs.addTab(self.tab_demandes, "⌛ Demandes")
        self.demandes_tab_index = 1
        self.tabs.addTab(self.tab_planning, "📅 Planning")
        self.tabs.addTab(self.tab_residents, "👤 Résidents")
        self.tabs.addTab(self.tab_familles, "👨‍👩‍👧 Familles")
        
        # Onglet Statistiques
        self.tab_stats = VisioStatsWidget()
        self.tabs.addTab(self.tab_stats, "📊 Statistiques")
        
        # Mettre à jour le badge de notification
        self.update_demandes_badge()
        
        main_layout.addWidget(self.tabs)
        
        # Boutons du bas
        bottom_layout = QHBoxLayout()
        
        # Bouton Config Email
        btn_config_email = QPushButton("⚙️ Config Email")
        btn_config_email.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 16px;
                padding: 12px;
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        btn_config_email.clicked.connect(self.open_email_config)
        bottom_layout.addWidget(btn_config_email)
        
        bottom_layout.addStretch()
        
        # Bouton Retour
        btn_retour = QPushButton("🏠 Retour Accueil")
        btn_retour.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 18px;
                padding: 15px;
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        btn_retour.clicked.connect(self.back_requested.emit)
        bottom_layout.addWidget(btn_retour)
        
        main_layout.addLayout(bottom_layout)
    
    def create_inscriptions_tab(self):
        """Crée l'onglet Inscriptions en attente"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # En-tête
        title = QLabel("📋 INSCRIPTIONS EN ATTENTE DE VALIDATION")
        title.setStyleSheet("""
            QLabel {
                font-family: 'Poetsen One', sans-serif;
                font-size: 24px;
                color: #9b59b6;
                margin: 10px;
            }
        """)
        layout.addWidget(title)
        
        # Tableau des inscriptions
        self.table_inscriptions = QTableWidget()
        self.table_inscriptions.setColumnCount(7)
        self.table_inscriptions.setHorizontalHeaderLabels([
            "Date inscription", "Nom", "Prénom", "Résident", "Lien", "Email", "Actions"
        ])
        self.table_inscriptions.setSelectionMode(QTableWidget.NoSelection)
        self.table_inscriptions.setFocusPolicy(Qt.NoFocus)
        
        header = self.table_inscriptions.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self.table_inscriptions.setColumnWidth(6, 200)
        
        self.table_inscriptions.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a2e;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #9b59b6;
                color: white;
                font-weight: bold;
                padding: 10px;
            }
        """)
        layout.addWidget(self.table_inscriptions)
        
        return widget
    
    def create_demandes_tab(self):
        """Crée l'onglet Demandes en attente"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # En-tête avec titre et bouton rafraîchir
        header_layout = QHBoxLayout()
        
        title = QLabel("⏳ DEMANDES EN ATTENTE")
        title.setStyleSheet("""
            QLabel {
                font-family: 'Poetsen One', sans-serif;
                font-size: 24px;
                color: #f39c12;
                margin: 10px;
            }
        """)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Tableau des demandes
        self.table_demandes = QTableWidget()
        self.table_demandes.setColumnCount(7)
        self.table_demandes.setHorizontalHeaderLabels([
            "Date demande", "Résident", "Famille", "Date souhaitée", "Durée", "Message", "Actions"
        ])
        self.table_demandes.setSelectionMode(QTableWidget.NoSelection)  # Pas de sélection (utilisation souris)
        self.table_demandes.setFocusPolicy(Qt.NoFocus)  # Pas de focus clavier
        # Configuration des colonnes
        header = self.table_demandes.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Fixed)  # Colonne Actions en taille fixe
        self.table_demandes.setColumnWidth(6, 95)  # Largeur fixe pour les boutons
        self.table_demandes.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a2e;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #f39c12;
                color: white;
                font-weight: bold;
                padding: 10px;
            }
        """)
        layout.addWidget(self.table_demandes)
        
        return widget
    
    def create_planning_tab(self):
        """Crée l'onglet Planning & Disponibilités"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # En-tête avec navigation de date
        header_layout = QHBoxLayout()
        
        # Titre avec nom de l'animatrice
        title = QLabel("📅 PLANNING & DISPONIBILITÉS - Céline Ronayne")
        title.setStyleSheet("""
            QLabel {
                font-family: 'Poetsen One', sans-serif;
                font-size: 24px;
                color: #6aedc3;
                margin: 10px;
            }
        """)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Plus de sélecteur de vue, on affiche directement le calendrier mensuel
        
        # Bouton Gérer disponibilités
        btn_dispo = QPushButton("⚙️ Mes Disponibilités")
        btn_dispo.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 14px;
                padding: 8px 15px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        btn_dispo.clicked.connect(self.open_disponibilites_dialog)
        header_layout.addWidget(btn_dispo)
        
        layout.addLayout(header_layout)
        
        # Afficher directement le calendrier mensuel style Outlook
        from core.widgets.planning_calendar import PlanningCalendarWidget
        self.calendar_widget = PlanningCalendarWidget(self)
        layout.addWidget(self.calendar_widget)
        
        return widget
    
    def create_residents_tab(self):
        """Crée l'onglet Résidents"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Boutons en haut
        buttons_layout = QHBoxLayout()
        
        # Bouton Ajouter résident
        btn_add = QPushButton("➕ Ajouter un résident")
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 16px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        btn_add.clicked.connect(self.add_resident)
        buttons_layout.addWidget(btn_add)
        
        layout.addLayout(buttons_layout)
        
        # Tableau des résidents
        self.table_residents = QTableWidget()
        self.table_residents.setColumnCount(6)
        self.table_residents.setHorizontalHeaderLabels([
            ["Nom", "Prénom", "Chambre", "Code d'accès", "Famille(s)", "Actions"
        ])
        self.table_residents.setSelectionMode(QTableWidget.NoSelection)
        self.table_residents.setFocusPolicy(Qt.NoFocus)
        
        # Configurer la largeur des colonnes
        header = self.table_residents.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Nom
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Prénom
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Chambre
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Famille(s)
        header.setSectionResizeMode(4, QHeaderView.Fixed)   # Actions
        self.table_residents.setColumnWidth(4, 80)
        
        self.table_residents.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a2e;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #9146ff;
                color: white;
                font-weight: bold;
                padding: 10px;
            }
        """)
        self.table_residents.cellDoubleClicked.connect(self.on_resident_double_clicked)
        layout.addWidget(self.table_residents)
        
        return widget
    
    def create_familles_tab(self):
        """Crée l'onglet Familles"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Boutons en haut
        buttons_layout = QHBoxLayout()
        
        # Bouton Ajouter famille
        btn_add = QPushButton("➕ Ajouter une famille")
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 16px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        btn_add.clicked.connect(self.add_famille)
        buttons_layout.addWidget(btn_add)
        
        layout.addLayout(buttons_layout)
        
        # Tableau des familles
        self.table_familles = QTableWidget()
        self.table_familles.setColumnCount(7)
        self.table_familles.setHorizontalHeaderLabels([
            "Nom", "Prénom", "Résident", "Lien", "Email", "Téléphone", "Actions"
        ])
        self.table_familles.setSelectionMode(QTableWidget.NoSelection)  # Pas de sélection (utilisation souris)
        self.table_familles.setFocusPolicy(Qt.NoFocus)  # Pas de focus clavier
        
        # Configurer la largeur des colonnes
        header = self.table_familles.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Nom
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Prénom
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Résident
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Lien
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # Email
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # Téléphone
        header.setSectionResizeMode(6, QHeaderView.Fixed)    # Actions
        self.table_familles.setColumnWidth(6, 150)  # Largeur fixe pour Actions
        self.table_familles.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a2e;
                color: white;
                font-family: 'Poetsen One', sans-serif;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #9146ff;
                color: white;
                font-weight: bold;
                padding: 10px;
            }
        """)
        layout.addWidget(self.table_familles)
        
        return widget
    
    
    def load_data(self):
        """Charge toutes les données"""
        self.load_inscriptions()
        self.load_demandes()
        self.load_planning()
        self.load_residents()
        self.load_familles()
    
    def load_demandes(self):
        """Charge les demandes en attente"""
        db = SessionLocal()
        try:
            # Demandes avec statut "En attente"
            demandes = db.query(RendezVous).filter(
                RendezVous.statut == "En attente"
            ).order_by(RendezVous.created_at.desc()).all()
            
            self.table_demandes.setRowCount(len(demandes))
            
            for row, demande in enumerate(demandes):
                resident = db.query(Resident).get(demande.resident_id)
                famille = db.query(Famille).get(demande.famille_id)
                
                # Date de la demande (convertir UTC vers heure locale)
                created_local = self.utc_to_local(demande.created_at)
                self.table_demandes.setItem(row, 0, QTableWidgetItem(
                    created_local.strftime("%d/%m/%Y %H:%M")
                ))
                
                # Résident
                self.table_demandes.setItem(row, 1, QTableWidgetItem(
                    f"{resident.prenom} {resident.nom}"
                ))
                
                # Famille
                self.table_demandes.setItem(row, 2, QTableWidgetItem(
                    f"{famille.prenom} {famille.nom}"
                ))
                
                # Date souhaitée avec indication si passée
                date_rdv_text = demande.date_rdv.strftime("%d/%m/%Y %H:%M")
                if demande.date_rdv < datetime.now():
                    date_rdv_text += " ⚠️ Passé"
                self.table_demandes.setItem(row, 3, QTableWidgetItem(date_rdv_text))
                
                # Durée
                self.table_demandes.setItem(row, 4, QTableWidgetItem(
                    f"{demande.duree_minutes} min"
                ))
                
                # Message
                self.table_demandes.setItem(row, 5, QTableWidgetItem(
                    demande.notes_avant or ""
                ))
                
                # Boutons d'action
                actions_widget = QWidget()
                actions_widget.setStyleSheet("background-color: transparent;")
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(0, 0, 0, 0)
                actions_layout.setSpacing(5)
                actions_layout.setAlignment(Qt.AlignCenter)
                
                # Bouton Accepter (Vert)
                btn_accept = QPushButton("✅")
                btn_accept.setToolTip("Valider la demande")
                btn_accept.setCursor(Qt.PointingHandCursor)
                btn_accept.setFixedSize(40, 30)
                btn_accept.setStyleSheet("""
                    QPushButton {
                        background-color: #2ecc71;
                        color: white;
                        border: 2px solid #1e8449;
                        border-radius: 5px;
                        font-size: 16px;
                    }
                    QPushButton:hover {
                        background-color: #27ae60;
                        border: 2px solid #145a32;
                    }
                    QPushButton:focus {
                        background-color: #27ae60;
                        border: 3px solid #ffff00;
                    }
                """)
                btn_accept.clicked.connect(lambda checked, d=demande: self.accept_demande(d))
                actions_layout.addWidget(btn_accept)
                
                # Bouton Refuser (Rouge)
                btn_refuse = QPushButton("❌")
                btn_refuse.setToolTip("Refuser la demande")
                btn_refuse.setCursor(Qt.PointingHandCursor)
                btn_refuse.setFixedSize(40, 30)
                btn_refuse.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        border: 2px solid #a93226;
                        border-radius: 5px;
                        font-size: 16px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                        border: 2px solid #7b241c;
                    }
                    QPushButton:focus {
                        background-color: #c0392b;
                        border: 3px solid #ffff00;
                    }
                """)
                btn_refuse.clicked.connect(lambda checked, d=demande: self.refuse_demande(d))
                actions_layout.addWidget(btn_refuse)
                
                self.table_demandes.setCellWidget(row, 6, actions_widget)
        
        finally:
            db.close()
        
        # Mettre à jour le badge de notification
        self.update_demandes_badge()
    
    def load_inscriptions(self):
        """Charge les inscriptions en attente de validation"""
        db = SessionLocal()
        try:
            # Familles avec actif=False (en attente)
            inscriptions = db.query(Famille).filter(
                Famille.actif == False
            ).order_by(Famille.created_at.desc()).all()
            
            self.table_inscriptions.setRowCount(len(inscriptions))
            
            for row, famille in enumerate(inscriptions):
                resident = db.query(Resident).get(famille.resident_id)
                
                # Date d'inscription
                created_local = self.utc_to_local(famille.created_at) if famille.created_at else datetime.now()
                self.table_inscriptions.setItem(row, 0, QTableWidgetItem(
                    created_local.strftime("%d/%m/%Y %H:%M")
                ))
                
                # Nom
                self.table_inscriptions.setItem(row, 1, QTableWidgetItem(famille.nom))
                
                # Prénom
                self.table_inscriptions.setItem(row, 2, QTableWidgetItem(famille.prenom))
                
                # Résident
                self.table_inscriptions.setItem(row, 3, QTableWidgetItem(
                    f"{resident.prenom} {resident.nom}"
                ))
                
                # Lien
                self.table_inscriptions.setItem(row, 4, QTableWidgetItem(famille.lien_parente or ""))
                
                # Email
                self.table_inscriptions.setItem(row, 5, QTableWidgetItem(famille.email))
                
                # Boutons d'action
                actions_widget = QWidget()
                actions_widget.setStyleSheet("background-color: transparent;")
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(0, 0, 0, 0)
                actions_layout.setSpacing(5)
                actions_layout.setAlignment(Qt.AlignCenter)
                
                # Bouton Valider
                btn_validate = QPushButton("✅ Valider")
                btn_validate.setToolTip("Valider l'inscription")
                btn_validate.setCursor(Qt.PointingHandCursor)
                btn_validate.setFixedSize(90, 30)
                btn_validate.setStyleSheet("""
                    QPushButton {
                        background-color: #2ecc71;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        font-size: 14px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #27ae60;
                    }
                """)
                btn_validate.clicked.connect(lambda checked, f=famille: self.validate_inscription(f))
                actions_layout.addWidget(btn_validate)
                
                # Bouton Refuser
                btn_refuse = QPushButton("❌ Refuser")
                btn_refuse.setToolTip("Refuser l'inscription")
                btn_refuse.setCursor(Qt.PointingHandCursor)
                btn_refuse.setFixedSize(90, 30)
                btn_refuse.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        font-size: 14px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                """)
                btn_refuse.clicked.connect(lambda checked, f=famille: self.refuse_inscription(f))
                actions_layout.addWidget(btn_refuse)
                
                self.table_inscriptions.setCellWidget(row, 6, actions_widget)
            
            # Mettre à jour le badge
            self.update_inscriptions_badge()
        
        finally:
            db.close()
    
    def update_inscriptions_badge(self):
        """Met à jour le badge de notification sur l'onglet Inscriptions"""
        db = SessionLocal()
        try:
            count = db.query(Famille).filter(Famille.actif == False).count()
            
            if count > 0:
                self.tabs.setTabText(self.inscriptions_tab_index, f"📋 Inscriptions ({count})")
            else:
                self.tabs.setTabText(self.inscriptions_tab_index, "📋 Inscriptions")
        
        finally:
            db.close()
    
    def validate_inscription(self, famille):
        """Valide une inscription"""
        reply = QMessageBox.question(
            self,
            "Valider l'inscription",
            f"Voulez-vous valider l'inscription de {famille.prenom} {famille.nom} ?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                # Récupérer la famille depuis la DB
                famille_db = db.query(Famille).get(famille.id)
                famille_db.actif = True
                db.commit()
                
                # Envoyer email de confirmation
                self.send_validation_email(famille)
                
                # Rafraîchir immédiatement
                self.load_inscriptions()
                self.load_familles()
                
                QMessageBox.information(
                    self,
                    "✅ Inscription validée",
                    f"L'inscription de {famille.prenom} {famille.nom} a été validée.\nUn email de confirmation a été envoyé."
                )
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la validation:\n{str(e)}")
            
            finally:
                db.close()
    
    def refuse_inscription(self, famille):
        """Refuse une inscription"""
        reply = QMessageBox.question(
            self,
            "Refuser l'inscription",
            f"Voulez-vous refuser l'inscription de {famille.prenom} {famille.nom} ?\nLe compte sera supprimé.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                # Envoyer email de refus avant de supprimer
                self.send_refusal_email(famille)
                
                db.delete(famille)
                db.commit()
                
                QMessageBox.information(
                    self,
                    "❌ Inscription refusée",
                    f"L'inscription de {famille.prenom} {famille.nom} a été refusée.\nUn email a été envoyé."
                )
                
                self.load_inscriptions()
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(self, "Erreur", f"Erreur lors du refus:\n{str(e)}")
            
            finally:
                db.close()
    
    def send_validation_email(self, famille):
        """Envoie un email de validation"""
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; }}
                    .header {{ background-color: #2ecc71; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background-color: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .button {{ display: inline-block; background-color: #2ecc71; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-size: 18px; font-weight: bold; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✅ Votre compte est activé !</h1>
                        <p>{email_service.ehpad_name}</p>
                    </div>
                    <div class="content">
                        <p>Bonjour {famille.prenom} {famille.nom},</p>
                        
                        <p>Bonne nouvelle ! Votre inscription a été validée par notre équipe.</p>
                        
                        <p>Vous pouvez maintenant vous connecter au portail familles et demander des rendez-vous visio avec votre proche.</p>
                        
                        <div style="text-align: center;">
                            <a href="https://mely-portail.vercel.app" class="button">🌐 Accéder au Portail</a>
                        </div>
                        
                        <p><strong>Vos identifiants :</strong></p>
                        <p>📧 Email : {famille.email}<br>
                        🔑 Mot de passe : celui que vous avez choisi lors de l'inscription</p>
                        
                        <p>À bientôt !</p>
                        <p><strong>L'équipe {email_service.ehpad_name}</strong></p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            email_service.send_email(
                famille.email,
                f"✅ Votre compte {email_service.ehpad_name} est activé !",
                html_content
            )
            print(f"📧 Email de validation envoyé à {famille.email}")
        
        except Exception as e:
            print(f"❌ Erreur envoi email validation: {e}")
    
    def send_refusal_email(self, famille):
        """Envoie un email de refus"""
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; }}
                    .header {{ background-color: #e74c3c; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background-color: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Inscription non validée</h1>
                        <p>{email_service.ehpad_name}</p>
                    </div>
                    <div class="content">
                        <p>Bonjour {famille.prenom} {famille.nom},</p>
                        
                        <p>Nous avons bien reçu votre demande d'inscription au portail familles.</p>
                        
                        <p>Malheureusement, nous ne pouvons pas valider votre inscription pour le moment.</p>
                        
                        <p>Pour plus d'informations, n'hésitez pas à contacter directement l'établissement.</p>
                        
                        <p>Cordialement,</p>
                        <p><strong>L'équipe {email_service.ehpad_name}</strong></p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            email_service.send_email(
                famille.email,
                f"Votre demande d'inscription - {email_service.ehpad_name}",
                html_content
            )
            print(f"📧 Email de refus envoyé à {famille.email}")
        
        except Exception as e:
            print(f"❌ Erreur envoi email refus: {e}")
    
    def update_demandes_badge(self):
        """Met à jour le badge de notification sur l'onglet Demandes"""
        db = SessionLocal()
        try:
            # Compter les demandes en attente
            count = db.query(RendezVous).filter(
                RendezVous.statut == "En attente"
            ).count()
            
            # Mettre à jour le texte de l'onglet
            if count > 0:
                self.tabs.setTabText(self.demandes_tab_index, f"⌛ Demandes ({count})")
            else:
                self.tabs.setTabText(self.demandes_tab_index, "⌛ Demandes")
        
        finally:
            db.close()
    
    def load_planning(self):
        """Fonction vide, le calendrier gère tout"""
        pass
    
    def load_residents(self):
        """Charge la liste des résidents"""
        db = SessionLocal()
        try:
            residents = db.query(Resident).filter(Resident.actif == True).all()
            
            self.table_residents.setRowCount(len(residents))
            
            for row, resident in enumerate(residents):
                self.table_residents.setItem(row, 0, QTableWidgetItem(resident.nom))
                self.table_residents.setItem(row, 1, QTableWidgetItem(resident.prenom))
                self.table_residents.setItem(row, 3, QTableWidgetItem(resident.code_acces or "Aucun"))
                self.table_residents.setItem(row, 4, QTableWidgetItem(resident.chambre or ""))
                
                # Compter les familles
                familles_count = db.query(Famille).filter(
                    Famille.resident_id == resident.id,
                    Famille.actif == True
                ).count()
                self.table_residents.setItem(row, 4, QTableWidgetItem(str(familles_count)))
                
                # Boutons d'action
                actions_widget = QWidget()
                actions_widget.setStyleSheet("background-color: transparent;")
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(5, 5, 5, 5)
                actions_layout.setSpacing(5)
                actions_layout.setAlignment(Qt.AlignCenter)
                
                # Bouton Modifier
                btn_edit = QPushButton("✏️")
                btn_edit.setToolTip("Modifier ce résident")
                btn_edit.setCursor(Qt.PointingHandCursor)
                btn_edit.setFixedSize(25, 25)
                btn_edit.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #2980b9;
                    }
                """)
                btn_edit.clicked.connect(lambda checked, r=resident: self.edit_resident(r))
                actions_layout.addWidget(btn_edit)
                
                # Bouton Désactiver (vert)
                btn_deactivate = QPushButton("🟢")
                btn_deactivate.setToolTip("Désactiver ce résident (il n'apparaîtra plus sur le portail)")
                btn_deactivate.setCursor(Qt.PointingHandCursor)
                btn_deactivate.setFixedSize(25, 25)
                btn_deactivate.setStyleSheet("""
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #229954;
                    }
                """)
                btn_deactivate.clicked.connect(lambda checked, r=resident: self.deactivate_resident(r))
                actions_layout.addWidget(btn_deactivate)
                
                self.table_residents.setCellWidget(row, X, actions_widget)
        
        finally:
            db.close()
    
    def load_familles(self):
        """Charge la liste des familles"""
        db = SessionLocal()
        try:
            familles = db.query(Famille).filter(Famille.actif == True).all()
            
            self.table_familles.setRowCount(len(familles))
            
            for row, famille in enumerate(familles):
                self.table_familles.setItem(row, 0, QTableWidgetItem(famille.nom))
                self.table_familles.setItem(row, 1, QTableWidgetItem(famille.prenom))
                
                resident = db.query(Resident).get(famille.resident_id)
                self.table_familles.setItem(row, 2, QTableWidgetItem(
                    f"{resident.prenom} {resident.nom}"
                ))
                
                self.table_familles.setItem(row, 3, QTableWidgetItem(famille.lien_parente or ""))
                self.table_familles.setItem(row, 4, QTableWidgetItem(famille.email or ""))
                self.table_familles.setItem(row, 5, QTableWidgetItem(famille.telephone or ""))
                
                # Boutons d'action
                actions_widget = QWidget()
                actions_widget.setStyleSheet("background-color: transparent;")
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(5, 5, 5, 5)
                actions_layout.setSpacing(5)
                actions_layout.setAlignment(Qt.AlignCenter)
                
                # Bouton Modifier
                btn_edit = QPushButton("✏️")
                btn_edit.setToolTip("Modifier cette famille")
                btn_edit.setCursor(Qt.PointingHandCursor)
                btn_edit.setFixedSize(25, 25)
                btn_edit.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #2980b9;
                    }
                """)
                btn_edit.clicked.connect(lambda checked, f=famille: self.edit_famille(f))
                actions_layout.addWidget(btn_edit)
                
                # Bouton Supprimer
                btn_delete = QPushButton("🗑️")
                btn_delete.setToolTip("Supprimer cette famille")
                btn_delete.setCursor(Qt.PointingHandCursor)
                btn_delete.setFixedSize(25, 25)
                btn_delete.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                """)
                btn_delete.clicked.connect(lambda checked, f=famille: self.delete_famille(f))
                actions_layout.addWidget(btn_delete)
                
                self.table_residents.setCellWidget(row, 5, actions_widget)
        
        finally:
            db.close()
    
    def on_resident_double_clicked(self, row, column):
        """Gère le double-clic sur un résident pour le modifier"""
        db = SessionLocal()
        try:
            residents = db.query(Resident).filter(Resident.actif == True).all()
            if row < len(residents):
                resident = residents[row]
                self.edit_resident(resident)
        finally:
            db.close()
    
    
    def add_resident(self):
        """Ajoute un nouveau résident"""
        dialog = AddResidentDialog(self)
        dialog.resident_added.connect(self.load_residents)
        dialog.exec()

    def add_famille(self):
        """Ajoute une nouvelle famille"""
        dialog = AddFamilleDialog(self)
        dialog.famille_added.connect(self.load_familles)
        dialog.exec()

    def accept_demande(self, demande):
        """Accepte une demande de RDV"""
        reply = QMessageBox.question(
            self,
            "Confirmer l'acceptation",
            f"Accepter cette demande de rendez-vous ?\n\n"
            f"📅 Date : {demande.date_rdv.strftime('%d/%m/%Y à %H:%M')}\n"
            f"⏱️ Durée : {demande.duree_minutes} minutes",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                # Récupérer la demande depuis la DB pour éviter les problèmes de session
                demande_db = db.query(RendezVous).get(demande.id)
                if demande_db:
                    # Changer le statut en "Planifié"
                    demande_db.statut = "Planifié"
                    
                    # Générer le lien Jitsi si pas déjà fait
                    if not demande_db.lien_jitsi:
                        timestamp = demande_db.date_rdv.strftime("%Y%m%d%H%M%S")
                        demande_db.lien_jitsi = f"https://meet.jit.si/MelyEHPAD-{demande_db.resident_id}-{timestamp}"
                    
                    db.commit()
                    
                    print(f"✅ Demande acceptée pour RDV #{demande.id}")
                    
                    # Envoyer l'email de confirmation
                    if email_service.is_configured():
                        try:
                            email_service.send_rdv_confirmation(demande.id)
                            QMessageBox.information(
                                self,
                                "✅ Demande acceptée",
                                "Le rendez-vous a été confirmé.\n\n"
                                "📧 Un email de confirmation a été envoyé à la famille."
                            )
                        except:
                            QMessageBox.information(
                                self,
                                "✅ Demande acceptée",
                                "Le rendez-vous a été confirmé.\n\n"
                                "⚠️ L'email n'a pas pu être envoyé."
                            )
                    else:
                        QMessageBox.information(
                            self,
                            "✅ Demande acceptée",
                            "Le rendez-vous a été confirmé."
                        )
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de l'acceptation:\n{str(e)}"
                )
            
            finally:
                db.close()
                # Recharger les données APRÈS avoir fermé la session
                self.load_demandes()
                self.load_planning()
    
    def refuse_demande(self, demande):
        """Refuse une demande de RDV"""
        reply = QMessageBox.question(
            self,
            "Confirmer le refus",
            f"Refuser cette demande de rendez-vous ?\n\n"
            f"📅 Date : {demande.date_rdv.strftime('%d/%m/%Y à %H:%M')}\n\n"
            f"⚠️ La famille sera notifiée du refus.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                # Récupérer la demande depuis la DB pour éviter les problèmes de session
                demande_db = db.query(RendezVous).get(demande.id)
                if demande_db:
                    # Changer le statut en "Refusé"
                    demande_db.statut = "Refusé"
                    db.commit()
                    
                    print(f"❌ Demande refusée pour RDV #{demande.id}")
                    
                    QMessageBox.information(
                        self,
                        "Demande refusée",
                        "La demande a été refusée.\n\n"
                        "💡 Vous pouvez contacter la famille pour proposer un autre créneau."
                    )
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors du refus:\n{str(e)}"
                )
            
            finally:
                db.close()
                # Recharger les demandes APRÈS avoir fermé la session
                self.load_demandes()
    
    def edit_resident(self, resident):
        """Modifie un résident"""
        from core.widgets.visio_dialogs_edit import EditResidentDialog
        
        dialog = EditResidentDialog(resident, self)
        if dialog.exec():
            # Recharger la liste
            self.load_residents()
            QMessageBox.information(
                self,
                "✅ Résident modifié",
                f"{resident.prenom} {resident.nom} a été modifié avec succès."
            )
    
    def deactivate_resident(self, resident):
        """Désactive un résident (il n'apparaîtra plus sur le portail)"""
        reply = QMessageBox.question(
            self,
            "Confirmer la désactivation",
            f"Voulez-vous désactiver {resident.prenom} {resident.nom} ?\n\n"
            f"Le résident n'apparaîtra plus sur le portail en ligne.\n"
            f"Les familles déjà inscrites garderont leur accès.\n\n"
            f"💡 Pensez à synchroniser après avec SYNCHRONISER_RESIDENTS.bat",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                # Récupérer l'objet résident depuis la DB
                resident_db = db.query(Resident).get(resident.id)
                
                if resident_db:
                    # Désactiver le résident
                    resident_db.actif = False
                    db.commit()
                    
                    print(f"🟢 Résident #{resident.id} désactivé : {resident.prenom} {resident.nom}")
                    
                    # Recharger la liste
                    self.load_residents()
                    
                    QMessageBox.information(
                        self,
                        "✅ Résident désactivé",
                        f"{resident.prenom} {resident.nom} a été désactivé.\n\n"
                        f"💡 Lancez SYNCHRONISER_RESIDENTS.bat pour mettre à jour le portail."
                    )
                else:
                    QMessageBox.warning(self, "Erreur", "Résident introuvable")
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de la désactivation:\n{str(e)}"
                )
            
            finally:
                db.close()
    
    def delete_famille(self, famille):
        """Supprime une famille"""
        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Voulez-vous vraiment supprimer {famille.prenom} {famille.nom} ?\n\n"
            f"⚠️ Cette action est irréversible !",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                # Récupérer l'objet famille depuis la DB
                famille_db = db.query(Famille).get(famille.id)
                
                if famille_db:
                    # Supprimer vraiment (avec cascade : RDV)
                    db.delete(famille_db)
                    db.commit()
                    
                    print(f"🗑️ Famille #{famille.id} supprimée (avec RDV)")
                    
                    # Recharger la liste
                    self.load_familles()
                    
                    QMessageBox.information(
                        self,
                        "✅ Famille supprimée",
                        f"{famille.prenom} {famille.nom} a été supprimé(e) avec tous ses RDV."
                    )
                else:
                    QMessageBox.warning(self, "Erreur", "Famille introuvable")
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de la suppression:\n{str(e)}"
                )
            
            finally:
                db.close()
    
    def edit_famille(self, famille):
        """Modifie une famille"""
        from core.widgets.visio_dialogs_edit import EditFamilleDialog
        
        dialog = EditFamilleDialog(famille, self)
        if dialog.exec():
            # Recharger la liste
            self.load_familles()
            QMessageBox.information(
            f"⚠️ Cette action est irréversible !",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                # Récupérer l'objet résident depuis la DB
                resident_db = db.query(Resident).get(resident.id)
                
                if resident_db:
                    # Supprimer d'abord les RDV
                    rdvs = db.query(RendezVous).filter(RendezVous.resident_id == resident_db.id).all()
                    for rdv in rdvs:
                        db.delete(rdv)
                    
                    # Supprimer ensuite les familles
                    familles = db.query(Famille).filter(Famille.resident_id == resident_db.id).all()
                    for famille in familles:
                        db.delete(famille)
                    
                    # Enfin supprimer le résident
                    db.delete(resident_db)
                    db.commit()
                    
                    print(f"🗑️ Résident #{resident.id} supprimé avec {len(familles)} famille(s) et {len(rdvs)} RDV")
                    
                    # Recharger la liste
                    self.load_residents()
                    
                    QMessageBox.information(
                        self,
                        "✅ Résident supprimé",
                        f"{resident.prenom} {resident.nom} a été supprimé avec toutes ses familles et RDV."
                    )
                else:
                    QMessageBox.warning(self, "Erreur", "Résident introuvable")
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de la suppression:\n{str(e)}"
                )
            
            finally:
                db.close()
    
    def start_call(self, rdv):
        """Lance un appel vidéo"""
        print(f"📞 Lancement appel pour RDV #{rdv.id}")
        
        # Ouvrir le lien Jitsi dans le navigateur
        if rdv.lien_jitsi:
            webbrowser.open(rdv.lien_jitsi)
            
            # Mettre à jour le statut
            db = SessionLocal()
            try:
                rdv.statut = "En cours"
                db.commit()
                self.load_planning()
            finally:
                db.close()
        else:
            QMessageBox.warning(self, "Erreur", "Aucun lien Jitsi généré pour ce RDV")
    
    def setup_focus_navigation(self):
        """Configure la navigation au clavier"""
        # Donner le focus initial au premier onglet
        self.tabs.setCurrentIndex(0)
        current_widget = self.tabs.currentWidget()
        
        # Chercher le premier tableau et lui donner le focus
        for table in current_widget.findChildren(QTableWidget):
            table.setFocus()
            if table.rowCount() > 0:
                table.selectRow(0)
            break
    
    def keyPressEvent(self, event: QKeyEvent):
        """Gestion des touches clavier améliorée"""
        key = event.key()
        modifiers = event.modifiers()
        focused = self.focusWidget()
        
        # Échap pour retour
        if key == Qt.Key_Escape:
            print("🔙 Touche Échap - Retour à l'accueil")
            self.back_requested.emit()
            event.accept()
            return
        
        # Touche C pour configuration email
        if key == Qt.Key_C and not isinstance(focused, (QLineEdit, QTextEdit)):
            print("⚙️ Touche C - Configuration email")
            self.open_email_config()
            event.accept()
            return
        
        # Touche R pour rafraîchir les statistiques
        if key == Qt.Key_R and not isinstance(focused, (QLineEdit, QTextEdit)):
            if self.tabs.currentIndex() == 5:  # Onglet Statistiques
                print("🔄 Touche R - Rafraîchissement des statistiques")
                self.tab_stats.load_stats()
                event.accept()
                return
        
        # Tab pour naviguer entre onglets (simple et efficace)
        if key == Qt.Key_Tab and not (modifiers & Qt.ControlModifier):
            if modifiers & Qt.ShiftModifier:
                # Shift+Tab = onglet précédent
                self.previous_tab()
            else:
                # Tab = onglet suivant
                self.next_tab()
            event.accept()
            return
        
        # Flèches gauche/droite TOUJOURS pour changer d'onglet
        if key == Qt.Key_Left and not isinstance(focused, (QLineEdit, QTextEdit, QComboBox, QDateTimeEdit)):
            self.previous_tab()
            event.accept()
            return
        
        if key == Qt.Key_Right and not isinstance(focused, (QLineEdit, QTextEdit, QComboBox, QDateTimeEdit)):
            self.next_tab()
            event.accept()
            return
        
        # Flèches haut/bas pour naviguer dans les tableaux
        if key == Qt.Key_Up:
            self.navigate_table_up()
            event.accept()
            return
        
        if key == Qt.Key_Down:
            self.navigate_table_down()
            event.accept()
            return
        
        # Entrée pour valider
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if isinstance(focused, QPushButton):
                focused.click()
                event.accept()
                return
            
            # Si dans un tableau, chercher le bouton d'action
            if isinstance(focused, QTableWidget):
                current_row = focused.currentRow()
                if current_row >= 0:
                    # Chercher un bouton dans la ligne
                    for col in range(focused.columnCount()):
                        widget = focused.cellWidget(current_row, col)
                        if widget:
                            buttons = widget.findChildren(QPushButton)
                            if buttons:
                                buttons[0].click()  # Cliquer sur le premier bouton
                                event.accept()
                                return
        
        # Passer l'événement au parent si non géré
        super().keyPressEvent(event)
    
    def next_tab(self):
        """Passe à l'onglet suivant"""
        current = self.tabs.currentIndex()
        next_index = (current + 1) % self.tabs.count()
        self.tabs.setCurrentIndex(next_index)
        self.focus_current_tab()
        print(f"📑 Onglet : {self.tabs.tabText(next_index)}")
    
    def previous_tab(self):
        """Passe à l'onglet précédent"""
        current = self.tabs.currentIndex()
        prev_index = (current - 1) % self.tabs.count()
        self.tabs.setCurrentIndex(prev_index)
        self.focus_current_tab()
        print(f"📑 Onglet : {self.tabs.tabText(prev_index)}")
    
    def focus_current_tab(self):
        """Donne le focus au contenu de l'onglet actuel"""
        current_widget = self.tabs.currentWidget()
        
        # Chercher un tableau
        tables = current_widget.findChildren(QTableWidget)
        if tables:
            tables[0].setFocus()
            if tables[0].rowCount() > 0:
                tables[0].selectRow(0)
            return
        
        # Sinon chercher un bouton
        buttons = current_widget.findChildren(QPushButton)
        if buttons:
            buttons[0].setFocus()
    
    def navigate_table_up(self):
        """Navigation vers le haut dans un tableau"""
        current_widget = self.tabs.currentWidget()
        tables = current_widget.findChildren(QTableWidget)
        
        if not tables:
            return
        
        table = tables[0]
        
        # Si le tableau n'a pas le focus, lui donner
        if not table.hasFocus():
            table.setFocus()
            if table.rowCount() > 0:
                table.selectRow(0)
            return
        
        # Sinon naviguer normalement
        current_row = table.currentRow()
        if current_row > 0:
            table.selectRow(current_row - 1)
        else:
            # Boucler vers la dernière ligne
            if table.rowCount() > 0:
                table.selectRow(table.rowCount() - 1)
    
    def navigate_table_down(self):
        """Navigation vers le bas dans un tableau"""
        current_widget = self.tabs.currentWidget()
        tables = current_widget.findChildren(QTableWidget)
        
        if not tables:
            return
        
        table = tables[0]
        
        # Si le tableau n'a pas le focus, lui donner
        if not table.hasFocus():
            table.setFocus()
            if table.rowCount() > 0:
                table.selectRow(0)
            return
        
        # Sinon naviguer normalement
        current_row = table.currentRow()
        if current_row < table.rowCount() - 1:
            table.selectRow(current_row + 1)
        else:
            # Boucler vers la première ligne
            table.selectRow(0)
    
    def open_email_config(self):
        """Ouvre le dialogue de configuration email"""
        dialog = EmailConfigDialog(self)
        dialog.config_saved.connect(self.on_email_config_saved)
        dialog.exec()
    
    def on_email_config_saved(self):
        """Appelé quand la configuration email est sauvegardée"""
        QMessageBox.information(
            self,
            "✅ Configuration enregistrée",
            "La configuration email a été enregistrée avec succès !\n\n"
            "Les emails de confirmation seront maintenant envoyés automatiquement."
        )
    
    def setup_auto_refresh(self):
        """Configure le rafraîchissement automatique de tous les onglets"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.auto_refresh_all)
        # Rafraîchir toutes les 30 secondes
        self.refresh_timer.start(30000)
        print("🔄 Rafraîchissement automatique activé (toutes les 30 secondes)")
    
    def auto_refresh_all(self):
        """Rafraîchit automatiquement tous les onglets"""
        self.load_demandes()
        # Rafraîchir le calendrier
        if hasattr(self, 'calendar_widget'):
            self.calendar_widget.load_month()
        self.load_residents()
        self.load_familles()
        print("🔄 Rafraîchissement automatique effectué")
    
    def refresh_demandes(self):
        """Rafraîchit la liste des demandes en attente et le planning"""
        self.load_demandes()
        self.load_planning()
    
    def refresh_planning(self):
        """Rafraîchit manuellement le planning (bouton)"""
        self.load_planning()
        self.load_demandes()
        # Afficher un message temporaire
        from PySide6.QtWidgets import QApplication
        QApplication.instance().processEvents()
        print("🔄 Planning rafraîchi manuellement")
    
    def utc_to_local(self, utc_dt):
        """Convertit une datetime UTC en heure locale"""
        if utc_dt is None:
            return None
        # Si la datetime n'a pas de timezone, on assume qu'elle est en UTC
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        # Convertir en heure locale
        return utc_dt.astimezone()
    
    def change_planning_view(self, view):
        """Change la vue du planning (Aujourd'hui/Semaine/Mois)"""
        print(f"📅 Changement de vue : {view}")
        
        if view == "Mois":
            # Afficher le calendrier mensuel
            self.show_calendar_view()
        elif view == "Semaine":
            self.load_planning_semaine()
        else:  # Aujourd'hui
            self.load_planning()
    
    def show_calendar_view(self):
        """Affiche la vue calendrier mensuelle"""
        from core.widgets.planning_calendar import PlanningCalendarWidget
        
        # Cacher le tableau actuel
        self.table_planning.hide()
        
        # Créer ou afficher le calendrier
        if not hasattr(self, 'calendar_widget'):
            self.calendar_widget = PlanningCalendarWidget(self)
            # Insérer après le tableau
            planning_tab = self.tabs.widget(1)  # Onglet Planning
            planning_tab.layout().addWidget(self.calendar_widget)
        else:
            self.calendar_widget.show()
            self.calendar_widget.load_month()
    
    def hide_calendar_view(self):
        """Cache la vue calendrier"""
        if hasattr(self, 'calendar_widget'):
            self.calendar_widget.hide()
        self.table_planning.show()
    
    def load_planning_mois(self):
        """Charge le planning du mois entier"""
        from ..models import Disponibilite
        import calendar
        
        db = SessionLocal()
        try:
            # Date actuelle
            today = self.current_planning_date
            year = today.year
            month = today.month
            
            # Mettre à jour le label de date
            mois_fr = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                       'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
            self.label_date_planning.setText(f"📆 {mois_fr[month - 1].capitalize()} {year}")
            
            # Récupérer tous les RDV du mois
            first_day = datetime(year, month, 1)
            if month == 12:
                last_day = datetime(year + 1, 1, 1)
            else:
                last_day = datetime(year, month + 1, 1)
            
            rdvs = db.query(RendezVous).filter(
                RendezVous.date_rdv >= first_day,
                RendezVous.date_rdv < last_day,
                RendezVous.statut.in_(["Planifié", "Confirmé", "En cours", "Terminé"])
            ).order_by(RendezVous.date_rdv).all()
            
            if len(rdvs) == 0:
                self.table_planning.setRowCount(1)
                info_item = QTableWidgetItem(f"ℹ️ Aucun rendez-vous prévu en {mois_fr[month - 1]} {year}")
                info_item.setBackground(Qt.darkBlue)
                self.table_planning.setItem(0, 0, info_item)
                self.table_planning.setSpan(0, 0, 1, 7)
                return
            
            # Afficher les RDV
            self.table_planning.setRowCount(len(rdvs))
            
            for row, rdv in enumerate(rdvs):
                # Date et heure
                date_item = QTableWidgetItem(rdv.date_rdv.strftime("%d/%m à %H:%M"))
                self.table_planning.setItem(row, 0, date_item)
                
                # Résident
                resident = db.query(Resident).get(rdv.resident_id)
                self.table_planning.setItem(row, 1, QTableWidgetItem(
                    f"{resident.prenom} {resident.nom}"
                ))
                
                # Famille
                famille = db.query(Famille).get(rdv.famille_id)
                self.table_planning.setItem(row, 2, QTableWidgetItem(
                    f"{famille.prenom} {famille.nom}"
                ))
                
                # Durée
                self.table_planning.setItem(row, 3, QTableWidgetItem(
                    f"{rdv.duree_minutes} min"
                ))
                
                # Statut avec couleur
                statut_item = QTableWidgetItem(rdv.statut)
                if rdv.statut == "Planifié":
                    statut_item.setBackground(Qt.blue)
                elif rdv.statut == "Confirmé":
                    statut_item.setBackground(Qt.darkGreen)
                elif rdv.statut == "En cours":
                    statut_item.setBackground(Qt.darkYellow)
                elif rdv.statut == "Terminé":
                    statut_item.setBackground(Qt.darkGray)
                self.table_planning.setItem(row, 4, statut_item)
                
                # Notes
                notes = rdv.notes_avant or ""
                self.table_planning.setItem(row, 5, QTableWidgetItem(notes[:50]))
                
                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(5, 2, 5, 2)
                
                if rdv.lien_jitsi and rdv.statut in ["Planifié", "Confirmé"]:
                    btn_visio = QPushButton("🎥")
                    btn_visio.setFixedSize(35, 35)
                    btn_visio.clicked.connect(lambda checked, r=rdv: webbrowser.open(r.lien_jitsi))
                    actions_layout.addWidget(btn_visio)
                
                self.table_planning.setCellWidget(row, 6, actions_widget)
        
        finally:
            db.close()
    
    def load_planning_semaine(self):
        """Charge le planning de la semaine"""
        from ..models import Disponibilite
        
        # Cacher le calendrier si affiché
        self.hide_calendar_view()
        
        db = SessionLocal()
        try:
            # Date actuelle
            today = self.current_planning_date
            # Trouver le lundi de la semaine
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)
            
            # Mettre à jour le label
            self.label_date_planning.setText(
                f"📆 Semaine du {monday.strftime('%d/%m')} au {sunday.strftime('%d/%m/%Y')}"
            )
            
            # Récupérer les RDV de la semaine
            rdvs = db.query(RendezVous).filter(
                RendezVous.date_rdv >= datetime.combine(monday, datetime.min.time()),
                RendezVous.date_rdv < datetime.combine(sunday + timedelta(days=1), datetime.min.time()),
                RendezVous.statut.in_(["Planifié", "Confirmé", "En cours", "Terminé"])
            ).order_by(RendezVous.date_rdv).all()
            
            if len(rdvs) == 0:
                self.table_planning.setRowCount(1)
                info_item = QTableWidgetItem("ℹ️ Aucun rendez-vous prévu cette semaine")
                info_item.setBackground(Qt.darkBlue)
                self.table_planning.setItem(0, 0, info_item)
                self.table_planning.setSpan(0, 0, 1, 7)
                return
            
            # Afficher les RDV (même format que vue mois)
            self.table_planning.setRowCount(len(rdvs))
            
            jours_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            
            for row, rdv in enumerate(rdvs):
                # Jour et heure
                jour = jours_fr[rdv.date_rdv.weekday()]
                date_item = QTableWidgetItem(f"{jour} {rdv.date_rdv.strftime('%d/%m à %H:%M')}")
                self.table_planning.setItem(row, 0, date_item)
                
                # Résident
                resident = db.query(Resident).get(rdv.resident_id)
                self.table_planning.setItem(row, 1, QTableWidgetItem(
                    f"{resident.prenom} {resident.nom}"
                ))
                
                # Famille
                famille = db.query(Famille).get(rdv.famille_id)
                self.table_planning.setItem(row, 2, QTableWidgetItem(
                    f"{famille.prenom} {famille.nom}"
                ))
                
                # Durée
                self.table_planning.setItem(row, 3, QTableWidgetItem(
                    f"{rdv.duree_minutes} min"
                ))
                
                # Statut
                statut_item = QTableWidgetItem(rdv.statut)
                if rdv.statut == "Planifié":
                    statut_item.setBackground(Qt.blue)
                elif rdv.statut == "Confirmé":
                    statut_item.setBackground(Qt.darkGreen)
                elif rdv.statut == "En cours":
                    statut_item.setBackground(Qt.darkYellow)
                elif rdv.statut == "Terminé":
                    statut_item.setBackground(Qt.darkGray)
                self.table_planning.setItem(row, 4, statut_item)
                
                # Notes
                notes = rdv.notes_avant or ""
                self.table_planning.setItem(row, 5, QTableWidgetItem(notes[:50]))
                
                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(5, 2, 5, 2)
                
                if rdv.lien_jitsi and rdv.statut in ["Planifié", "Confirmé"]:
                    btn_visio = QPushButton("🎥")
                    btn_visio.setFixedSize(35, 35)
                    btn_visio.clicked.connect(lambda checked, r=rdv: webbrowser.open(r.lien_jitsi))
                    actions_layout.addWidget(btn_visio)
                
                self.table_planning.setCellWidget(row, 6, actions_widget)
        
        finally:
            db.close()
    
    def open_disponibilites_dialog(self):
        """Ouvre le dialogue de gestion des disponibilités"""
        from .disponibilites_dialog_v2 import DisponibilitesDialogV2
        dialog = DisponibilitesDialogV2(self)
        dialog.disponibilites_updated.connect(lambda: self.calendar_widget.load_month() if hasattr(self, 'calendar_widget') else None)
        dialog.exec()
    
    def synchroniser_disponibilites(self):
        """Synchronise les disponibilités avec le cloud"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import os
        
        # URL de la base cloud
        DATABASE_URL = "postgresql://mely:zPN0ohFdKGq2ZL7XgE9WC5dG3CKQ24xh@dpg-d3njb8ruibrs738f2v00-a.oregon-postgres.render.com/mely_s9ai"
        
        # Message de confirmation
        reply = QMessageBox.question(
            self,
            "Synchronisation",
            "Voulez-vous synchroniser vos disponibilités avec le portail web ?\n\n"
            "Les familles verront vos nouveaux créneaux disponibles.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Afficher un message de chargement
        progress = QMessageBox(self)
        progress.setWindowTitle("Synchronisation en cours")
        progress.setText("🔄 Synchronisation avec le portail web...\n\nVeuillez patienter...")
        progress.setStandardButtons(QMessageBox.NoButton)
        progress.show()
        QApplication.processEvents()
        
        try:
            # Récupérer les disponibilités locales
            from ..models import Disponibilite
            local_db = SessionLocal()
            
            try:
                dispos = local_db.query(Disponibilite).filter(Disponibilite.actif == True).all()
                
                if not dispos:
                    progress.close()
                    QMessageBox.warning(
                        self,
                        "Aucune disponibilité",
                        "Aucune disponibilité à synchroniser.\n\n"
                        "Ajoutez des disponibilités dans '⚙️ Mes Disponibilités' d'abord."
                    )
                    return
                
                # Connexion au cloud
                cloud_engine = create_engine(DATABASE_URL)
                CloudSession = sessionmaker(bind=cloud_engine)
                cloud_db = CloudSession()
                
                try:
                    # Utiliser directement le modèle Disponibilite existant
                    from ..models import Disponibilite as CloudDispo
                    from sqlalchemy.ext.declarative import declarative_base
                    
                    # Créer la table si elle n'existe pas
                    Base = declarative_base()
                    CloudDispo.__table__.create(cloud_engine, checkfirst=True)
                    
                    # Supprimer les anciennes
                    cloud_db.execute("DELETE FROM disponibilites")
                    cloud_db.commit()
                    
                    # Ajouter les nouvelles
                    for d in dispos:
                        cloud_db.execute(
                            "INSERT INTO disponibilites (jour_semaine, heure_debut, heure_fin, type, actif) VALUES (:j, :hd, :hf, :t, :a)",
                            {
                                'j': d.jour_semaine,
                                'hd': d.heure_debut,
                                'hf': d.heure_fin,
                                't': d.type,
                                'a': d.actif
                            }
                        )
                    cloud_db.commit()
                    
                    progress.close()
                    
                    QMessageBox.information(
                        self,
                        "✅ Synchronisation réussie",
                        f"✅ {len(dispos)} disponibilités synchronisées !\n\n"
                        "Les familles peuvent maintenant voir vos créneaux sur le portail web."
                    )
                    
                finally:
                    cloud_db.close()
                    
            finally:
                local_db.close()
        
        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self,
                "❌ Erreur de synchronisation",
                f"Erreur lors de la synchronisation :\n\n{str(e)}\n\n"
                "Vérifiez votre connexion internet."
            )
    
    def finish_rdv(self, rdv):
        """Marque un RDV comme terminé"""
        reply = QMessageBox.question(
            self,
            "Terminer le RDV",
            f"Marquer ce rendez-vous comme terminé ?\n\n"
            f"👤 {rdv.resident.prenom} {rdv.resident.nom}\n"
            f"📅 {rdv.date_rdv.strftime('%d/%m/%Y à %H:%M')}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                rdv.statut = "Terminé"
                db.commit()
                
                QMessageBox.information(
                    self,
                    "✅ RDV terminé",
                    "Le rendez-vous a été marqué comme terminé."
                )
                
                self.load_planning()
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de la mise à jour:\n{str(e)}"
                )
            
            finally:
                db.close()
    
    def cancel_rdv(self, rdv):
        """Annule un RDV"""
        reply = QMessageBox.question(
            self,
            "Annuler le RDV",
            f"Êtes-vous sûr de vouloir annuler ce rendez-vous ?\n\n"
            f"👤 {rdv.resident.prenom} {rdv.resident.nom}\n"
            f"📅 {rdv.date_rdv.strftime('%d/%m/%Y à %H:%M')}\n\n"
            f"⚠️ La famille sera notifiée de l'annulation.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                rdv.statut = "Annulé"
                db.commit()
                
                QMessageBox.information(
                    self,
                    "❌ RDV annulé",
                    "Le rendez-vous a été annulé.\n\n"
                    "💡 Pensez à contacter la famille pour expliquer l'annulation."
                )
                
                self.load_planning()
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de l'annulation:\n{str(e)}"
                )
            
            finally:
                db.close()
    
    def delete_rdv(self, rdv):
        """Supprime un RDV"""
        reply = QMessageBox.question(
            self,
            "Supprimer le RDV",
            f"Voulez-vous vraiment SUPPRIMER ce rendez-vous ?\n\n"
            f"👤 {rdv.resident.prenom} {rdv.resident.nom}\n"
            f"📅 {rdv.date_rdv.strftime('%d/%m/%Y à %H:%M')}\n\n"
            f"⚠️ Cette action est irréversible !",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            db = SessionLocal()
            try:
                # Récupérer le RDV depuis la DB
                rdv_db = db.query(RendezVous).get(rdv.id)
                
                if rdv_db:
                    db.delete(rdv_db)
                    db.commit()
                    
                    QMessageBox.information(
                        self,
                        "✅ RDV supprimé",
                        "Le rendez-vous a été supprimé définitivement."
                    )
                    
                    self.load_planning()
                else:
                    QMessageBox.warning(self, "Erreur", "RDV introuvable")
            
            except Exception as e:
                db.rollback()
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de la suppression:\n{str(e)}"
                )
            
            finally:
                db.close()
    
    def sync_delete_famille_cloud(self, famille_id):
        """Supprime une famille dans le cloud (soft delete)"""
        import requests
        
        try:
            # URL de votre API cloud (à adapter selon votre déploiement)
            api_url = "https://mely-portail.vercel.app/api"  # Ou votre URL Render/Railway
            
            # Envoyer la requête de suppression
            response = requests.post(
                f"{api_url}/famille/{famille_id}/delete",
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"✅ Famille #{famille_id} supprimée du cloud")
            else:
                print(f"⚠️ Erreur cloud: {response.status_code}")
        
        except Exception as e:
            print(f"⚠️ Impossible de synchroniser avec le cloud: {e}")
            # Ne pas bloquer si le cloud est inaccessible
    
    def sync_to_cloud(self):
        """Synchronise les résidents vers le cloud via l'API"""
        import subprocess
        from pathlib import Path
        
        # Confirmation
        reply = QMessageBox.question(
            self,
            "Synchronisation Cloud",
            "Voulez-vous synchroniser les résidents vers le portail web ?\n\n"
            "Les familles verront les résidents mis à jour sur le portail.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Lancer le script de synchronisation
        try:
            script_path = Path(__file__).parent.parent.parent / "tools" / "sync_residents_via_api.py"
            
            # Afficher un message de chargement
            progress = QMessageBox(self)
            progress.setWindowTitle("Synchronisation")
            progress.setText("Synchronisation en cours...\n\nVeuillez patienter.")
            progress.setStandardButtons(QMessageBox.NoButton)
            progress.show()
            
            # Lancer le script
            result = subprocess.run(
                ["C:\\Python314\\python.exe", str(script_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            progress.close()
            
            if result.returncode == 0:
                QMessageBox.information(
                    self,
                    "Synchronisation réussie",
                    "✅ Les résidents ont été synchronisés avec succès !\n\n"
                    "Les familles peuvent maintenant les voir sur le portail."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Erreur de synchronisation",
                    f"❌ Erreur lors de la synchronisation :\n\n{result.stderr}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erreur",
                f"❌ Impossible de lancer la synchronisation :\n\n{str(e)}"
            )
    
    def sync_to_cloud_old(self):
        """Ancienne méthode de synchronisation (désactivée)"""
        pass
        
    def _old_sync_thread_run(self):
        """Ancien code de synchronisation - désactivé"""
        pass
