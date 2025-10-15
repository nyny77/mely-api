"""
API Cloud pour le portail familles
Version adaptée pour le déploiement (Railway/Heroku)
"""

import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./mely_cloud.db')
# Fix pour Heroku qui utilise postgres:// au lieu de postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

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

PORT = int(os.getenv('PORT', 8081))


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
        
        # Vérifier le code (pour l'instant, on accepte n'importe quel code de 4 chiffres)
        if len(code) != 4:
            return jsonify({'success': False, 'message': 'Code invalide'}), 401
        
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
        
        # Créer la demande de RDV avec statut "En attente"
        rdv = RendezVous(
            resident_id=resident_id,
            famille_id=famille_id,
            date_rdv=date_rdv,
            duree_minutes=duration,
            statut="En attente",
            notes_avant=message,
            rappel_envoye=False
        )
        
        db.add(rdv)
        db.commit()
        
        print(f"📝 Nouvelle demande de RDV créée : #{rdv.id}")
        
        return jsonify({
            'success': True,
            'message': 'Demande envoyée avec succès',
            'rdv_id': rdv.id
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
