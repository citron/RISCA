#!/bin/bash

# Script pour traiter toutes les données NM par semaine depuis 2008
# ATTENTION: Ce script peut prendre beaucoup de temps à s'exécuter

set -e  # Arrêter en cas d'erreur

DICOM_DIR="$HOME/dicom"
PREDICTIONS_DIR="$HOME/predictions"
PREDICTIONS_FILE="$PREDICTIONS_DIR/predictions.csv"

# Créer le répertoire de prédictions s'il n'existe pas
mkdir -p "$PREDICTIONS_DIR"

# Initialiser le fichier de prédictions (avec en-tête)
> "$PREDICTIONS_FILE"
header_written=false

# Date de début: 1er janvier 2008
start_date="2008-01-01"
# Date de fin: aujourd'hui
end_date=$(date +%Y-%m-%d)

# Convertir les dates en secondes depuis epoch
current=$(date -d "$start_date" +%s)
end=$(date -d "$end_date" +%s)

# Durée d'une semaine en secondes
week_seconds=$((7 * 24 * 60 * 60))

week_count=0

echo "Début du traitement de $start_date à $end_date"
echo "=========================================="

while [ $current -le $end ]; do
    # Calculer date de début de la semaine
    date_debut=$(date -d "@$current" +%Y%m%d)
    
    # Calculer date de fin de la semaine (6 jours plus tard)
    next=$((current + week_seconds - 86400))
    if [ $next -gt $end ]; then
        next=$end
    fi
    date_fin=$(date -d "@$next" +%Y%m%d)
    
    week_count=$((week_count + 1))
    
    echo ""
    echo "Semaine $week_count: $date_debut à $date_fin"
    echo "----------------------------------------"
    
    # Vider le répertoire dicom
    echo "Nettoyage de $DICOM_DIR..."
    rm -rf "$DICOM_DIR"
    mkdir -p "$DICOM_DIR"
    
    # Lancer la récupération et prédiction
    echo "Récupération des données..."
    if uv run pacs_nm_retriever.py --from-date "$date_debut" --to-date "$date_fin" -o "$DICOM_DIR/"; then
        # Exécuter risca.sh
        echo "Exécution de ~/risca.sh..."
        if [ -f "$HOME/risca.sh" ]; then
            "$HOME/risca.sh"
        else
            echo "ATTENTION: ~/risca.sh non trouvé"
        fi
        
        # Vérifier si un fichier predictions.csv a été généré
        if [ -f "$DICOM_DIR/predictions.csv" ]; then
            # Si c'est la première fois, copier l'en-tête
            if [ "$header_written" = false ]; then
                cat "$DICOM_DIR/predictions.csv" >> "$PREDICTIONS_FILE"
                header_written=true
                echo "Prédictions ajoutées (avec en-tête)"
            else
                # Sinon, ajouter seulement les données (sans la première ligne)
                tail -n +2 "$DICOM_DIR/predictions.csv" >> "$PREDICTIONS_FILE"
                echo "Prédictions ajoutées (sans en-tête)"
            fi
        else
            echo "ATTENTION: Aucun fichier predictions.csv trouvé pour cette période"
        fi
    else
        echo "ERREUR: La récupération a échoué pour la période $date_debut - $date_fin"
        # Continuer avec la semaine suivante même en cas d'erreur
    fi
    
    # Passer à la semaine suivante
    current=$((current + week_seconds))
done

echo ""
echo "=========================================="
echo "Traitement terminé!"
echo "Total de semaines traitées: $week_count"
echo "Fichier de prédictions: $PREDICTIONS_FILE"

# Compter le nombre de lignes dans le fichier final (moins l'en-tête)
if [ -f "$PREDICTIONS_FILE" ]; then
    total_predictions=$(($(wc -l < "$PREDICTIONS_FILE") - 1))
    echo "Total de prédictions: $total_predictions"
fi
