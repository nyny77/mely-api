"""
API Cloud pour le portail familles
Version adaptée pour le déploiement (Railway/Heroku)
"""

import os
import sys
import secrets
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Configuration de la base de données
# En production (Render), utiliser DATABASE_URL de l'environnement
# En local, utiliser SQLite
if os.getenv('DATABASE_URL'):
    # Render PostgreSQL
    DATABASE_URL = os.getenv('DATABASE_URL')
    # Fix pour Render qui utilise postgres:// au lieu de postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
else:
    # Local SQLite
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from portable_utils import get_portable_database_url
        DATABASE_URL = get_portable_database_url()
    except ImportError:
        DATABASE_URL = 'sqlite:///./mely.db'

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Modèles simplifiés
class Resident(Base):
    __tablename__ = "residents"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    chambre = Column(String)
    code_acces = Column(String, unique=True, index=True)
    actif = Column(Boolean, default=True)
    familles = relationship("Famille", back_populates="resident")
    rendez_vous = relationship("RendezVous", back_populates="resident")


class Famille(Base):
    __tablename__ = "familles"
    id = Column(Integer, primary_key=True, index=True)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=False)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    lien_parente = Column(String)
    email = Column(String, index=True)
    telephone = Column(String)
    mot_de_passe = Column(String)
    actif = Column(Boolean, default=True)
    resident = relationship("Resident", back_populates="familles")
    rendez_vous = relationship("RendezVous", back_populates="famille")


class RendezVous(Base):
    __tablename__ = "rendez_vous"
    id = Column(Integer, primary_key=True, index=True)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=False)
    famille_id = Column(Integer, ForeignKey("familles.id"), nullable=False)
    date_rdv = Column(DateTime, nullable=False, index=True)
    duree_minutes = Column(Integer, default=30)
    statut = Column(String, default="Planifié")
    notes_avant = Column(Text)
    lien_jitsi = Column(String)
    rappel_envoye = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    resident = relationship("Resident", back_populates="rendez_vous")
    famille = relationship("Famille", back_populates="rendez_vous")


class Disponibilite(Base):
    """Disponibilités de l'animatrice"""
    __tablename__ = "disponibilites"
    id = Column(Integer, primary_key=True, index=True)
    jour_semaine = Column(Integer, nullable=False)  # 0=Lundi, 6=Dimanche
    heure_debut = Column(String, nullable=False)  # Format HH:MM
    heure_fin = Column(String, nullable=False)  # Format HH:MM
    type = Column(String, default="Disponible")  # Disponible ou Bloqué
    actif = Column(Boolean, default=True)


# Créer les tables
Base.metadata.create_all(bind=engine)

# Flask app
app = Flask(__name__)
CORS(app)

PORT = int(os.getenv('PORT', 5000))


@app.route('/')
def home():
    """Page d'accueil de l'API"""
    return jsonify({
        'name': 'API Mely - Portail Familles',
        'version': '1.0.0',
        'status': 'online',
        'endpoints': {
            'login': 'POST /api/login',
            'rdv': 'GET /api/rdv/<famille_id>',
            'request': 'POST /api/rdv/request',
            'cancel': 'POST /api/rdv/<rdv_id>/cancel',
            'disponibilites': 'GET /api/disponibilites',
            'health': 'GET /api/health'
        }
    })


@app.route('/api/health', methods=['GET'])
def health():
    """Vérification de l'état du serveur"""
    return jsonify({'status': 'ok', 'message': 'API Mely opérationnelle'})


@app.route('/api/residents', methods=['GET'])
def get_residents():
    """Récupère la liste des résidents actifs"""
    db = SessionLocal()
    try:
        residents = db.query(Resident).filter(Resident.actif == True).order_by(Resident.nom, Resident.prenom).all()
        return jsonify({
            'success': True,
            'residents': [
                {
                    'id': r.id,
                    'nom': r.nom,
                    'prenom': r.prenom,
                    'chambre': r.chambre
                }
                for r in residents
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/residents/verify-code', methods=['POST'])
def verify_code():
    """Vérifie un code d'accès et retourne les infos du résident"""
    data = request.json
    code = data.get('code', '').strip().upper()
    
    if not code:
        return jsonify({'success': False, 'error': 'Code requis'}), 400
    
    db = SessionLocal()
    try:
        # Chercher le résident avec ce code
        resident = db.query(Resident).filter(
            Resident.code_acces == code,
            Resident.actif == True
        ).first()
        
        if resident:
            return jsonify({
                'success': True,
                'resident': {
                    'id': resident.id,
                    'nom': resident.nom,
                    'prenom': resident.prenom,
                    'chambre': resident.chambre
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Code invalide ou résident inactif'
            }), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/residents/sync', methods=['POST'])
def sync_resident():
    """Ajoute ou met à jour un résident (pour la synchronisation)"""
    data = request.json
    db = SessionLocal()
    try:
        # Vérifier si le résident existe déjà
        resident = db.query(Resident).filter(
            Resident.nom == data.get('nom'),
            Resident.prenom == data.get('prenom')
        ).first()
        
        if resident:
            # Mettre à jour
            resident.chambre = data.get('chambre')
            resident.code_acces = data.get('code_acces')
            resident.actif = data.get('actif', True)
            action = 'updated'
        else:
            # Créer nouveau
            resident = Resident(
                nom=data.get('nom'),
                prenom=data.get('prenom'),
                chambre=data.get('chambre'),
                code_acces=data.get('code_acces'),
                actif=data.get('actif', True)
            )
            db.add(resident)
            action = 'created'
        
        db.commit()
        return jsonify({
            'success': True,
            'action': action,
            'resident': {
                'id': resident.id,
                'nom': resident.nom,
                'prenom': resident.prenom,
                'chambre': resident.chambre
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/residents/<int:resident_id>/delete', methods=['POST'])
def delete_resident(resident_id):
    """Désactive un résident (soft delete)"""
    db = SessionLocal()
    try:
        resident = db.query(Resident).get(resident_id)
        if resident:
            resident.actif = False
            db.commit()
            return jsonify({'success': True, 'message': 'Résident désactivé'})
        else:
            return jsonify({'success': False, 'error': 'Résident non trouvé'}), 404
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/login', methods=['POST'])
def login():
    """Authentification d'une famille"""
    data = request.json
    email = data.get('email')
    code = data.get('code')
    
    db = SessionLocal()
    try:
        # Chercher la famille par email
        famille = db.query(Famille).filter(
            Famille.email == email,
            Famille.actif == True
        ).first()
        
        if not famille:
            return jsonify({'success': False, 'message': 'Email non trouvé'}), 401
        
        # Vérifier le mot de passe
        if not code or code != famille.mot_de_passe:
            return jsonify({'success': False, 'message': 'Mot de passe incorrect'}), 401
        
        # Récupérer le résident
        resident = db.query(Resident).get(famille.resident_id)
        
        return jsonify({
            'success': True,
            'famille': {
                'id': famille.id,
                'nom': famille.nom,
                'prenom': famille.prenom,
                'email': famille.email
            },
            'resident': {
                'id': resident.id,
                'nom': resident.nom,
                'prenom': resident.prenom,
                'chambre': resident.chambre
            }
        })
    
    finally:
        db.close()


@app.route('/api/rdv/<int:famille_id>', methods=['GET'])
def get_rdv(famille_id):
    """Récupère les RDV d'une famille"""
    db = SessionLocal()
    try:
        rdvs = db.query(RendezVous).filter(
            RendezVous.famille_id == famille_id,
            RendezVous.statut.in_(['Planifié', 'Confirmé', 'En attente'])
        ).order_by(RendezVous.date_rdv).all()
        
        rdv_list = []
        for rdv in rdvs:
            rdv_list.append({
                'id': rdv.id,
                'date': rdv.date_rdv.strftime('%Y-%m-%d'),
                'heure': rdv.date_rdv.strftime('%H:%M'),
                'duree': rdv.duree_minutes,
                'statut': rdv.statut,
                'lien': rdv.lien_jitsi
            })
        
        return jsonify({'success': True, 'rdvs': rdv_list})
    
    finally:
        db.close()


@app.route('/api/rdv/request', methods=['POST'])
def request_rdv():
    """Crée une demande de RDV"""
    data = request.json
    
    db = SessionLocal()
    try:
        # Récupérer les données
        famille_id = data.get('famille_id')
        resident_id = data.get('resident_id')
        date_str = data.get('date')
        time_str = data.get('time')
        duration = data.get('duration', 30)
        message = data.get('message', '')
        
        # Créer la date/heure
        date_rdv = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        
        # Générer un lien Jitsi unique
        room_id = secrets.token_urlsafe(16)
        jitsi_link = f"https://meet.jit.si/ehpad-crecy-{room_id}"
        
        # Créer la demande de RDV avec statut "En attente"
        rdv = RendezVous(
            resident_id=resident_id,
            famille_id=famille_id,
            date_rdv=date_rdv,
            duree_minutes=duration,
            statut="En attente",
            notes_avant=message,
            lien_jitsi=jitsi_link,
            rappel_envoye=False
        )
        
        db.add(rdv)
        db.commit()
        
        print(f"📝 Nouvelle demande de RDV créée : #{rdv.id}")
        print(f"🔗 Lien Jitsi généré : {jitsi_link}")
        
        return jsonify({
            'success': True,
            'message': 'Demande envoyée avec succès',
            'rdv_id': rdv.id,
            'jitsi_link': jitsi_link
        })
    
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur : {e}")
        return jsonify({
            'success': False,
            'message': f'Erreur : {str(e)}'
        }), 500
    
    finally:
        db.close()


@app.route('/api/rdv/<int:rdv_id>/cancel', methods=['POST'])
def cancel_rdv(rdv_id):
    """Annule un RDV"""
    db = SessionLocal()
    try:
        rdv = db.query(RendezVous).get(rdv_id)
        
        if not rdv:
            return jsonify({'success': False, 'message': 'RDV non trouvé'}), 404
        
        rdv.statut = "Annulé"
        db.commit()
        
        print(f"❌ RDV #{rdv_id} annulé")
        
        return jsonify({'success': True, 'message': 'RDV annulé'})
    
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
    finally:
        db.close()


@app.route('/api/disponibilites', methods=['GET'])
def get_disponibilites():
    """Récupère les disponibilités de l'animatrice avec les créneaux déjà demandés"""
    db = SessionLocal()
    try:
        # Récupérer toutes les disponibilités actives de type "Disponible"
        dispos = db.query(Disponibilite).filter(
            Disponibilite.actif == True,
            Disponibilite.type == "Disponible"
        ).order_by(Disponibilite.jour_semaine, Disponibilite.heure_debut).all()
        
        # Récupérer tous les RDV en attente ou confirmés
        rdvs = db.query(RendezVous).filter(
            RendezVous.statut.in_(['En attente', 'Planifié', 'Confirmé'])
        ).all()
        
        # Créer un set des créneaux déjà pris (date + heure)
        creneaux_pris = set()
        for rdv in rdvs:
            creneau_key = f"{rdv.date_rdv.strftime('%Y-%m-%d')}_{rdv.date_rdv.strftime('%H:%M')}"
            creneaux_pris.add(creneau_key)
        
        disponibilites = []
        for dispo in dispos:
            disponibilites.append({
                'id': dispo.id,
                'jour_semaine': dispo.jour_semaine,
                'heure_debut': dispo.heure_debut,
                'heure_fin': dispo.heure_fin,
                'type': dispo.type
            })
        
        return jsonify({
            'success': True,
            'disponibilites': disponibilites,
            'creneaux_pris': list(creneaux_pris)
        })
    
    except Exception as e:
        print(f"❌ Erreur get_disponibilites: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    
    finally:
        db.close()


@app.route('/api/famille/<int:famille_id>/delete', methods=['POST'])
def delete_famille(famille_id):
    """Supprime (désactive) une famille"""
    db = SessionLocal()
    try:
        famille = db.query(Famille).get(famille_id)
        
        if not famille:
            return jsonify({'success': False, 'message': 'Famille non trouvée'}), 404
        
        # Soft delete : désactiver au lieu de supprimer
        famille.actif = False
        db.commit()
        
        print(f"🗑️ Famille #{famille_id} désactivée")
        
        return jsonify({'success': True, 'message': 'Famille supprimée'})
    
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur delete_famille: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
    finally:
        db.close()


@app.route('/api/admin/migrate-add-code-acces', methods=['POST'])
def migrate_add_code_acces():
    """Route admin pour ajouter la colonne code_acces"""
    try:
        with engine.connect() as conn:
            # Vérifier si la colonne existe déjà
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='residents' AND column_name='code_acces'
            """))
            
            if result.fetchone():
                return jsonify({
                    'success': True,
                    'message': 'La colonne code_acces existe déjà'
                })
            else:
                # Ajouter la colonne
                conn.execute(text("ALTER TABLE residents ADD COLUMN code_acces VARCHAR UNIQUE"))
                conn.commit()
                return jsonify({
                    'success': True,
                    'message': 'Colonne code_acces ajoutée avec succès'
                })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
