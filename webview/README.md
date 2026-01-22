# Visualiseur DICOM

Serveur web en Rust pour visualiser les fichiers DICOM du répertoire `/home/gacquewi/dicom`.

## Fonctionnalités

- 🌐 Serveur web sur le port 8104
- 📁 Navigation dans l'arborescence des fichiers DICOM
- 🖼️ Visualisation des images DICOM
- ℹ️ Affichage des métadonnées DICOM (patient, date, modalité, dimensions)
- 🎨 Interface moderne et responsive

## Construction

```bash
./build.sh
```

Ou manuellement:

```bash
cargo build --bin server --release
```

## Lancement

```bash
./target/release/server
```

Le serveur démarrera sur http://localhost:8104

## Architecture

- **Backend**: Actix-web (Rust) avec la bibliothèque `dicom` pour lire les fichiers DICOM
- **Frontend**: HTML/CSS/JavaScript vanilla pour une interface réactive
- **API REST**:
  - `GET /api/files` - Liste les fichiers à la racine
  - `GET /api/files/{path}` - Liste les fichiers dans un sous-répertoire
  - `GET /api/dicom/info/{path}` - Récupère les métadonnées d'un fichier DICOM
  - `GET /api/dicom/image/{path}` - Récupère les données pixel d'une image DICOM

## Sécurité

- Le serveur ne permet l'accès qu'aux fichiers dans `/home/gacquewi/dicom`
- Protection contre les attaques de traversée de répertoire
- CORS configuré pour le développement

## Technologies

- Rust 1.92.0
- actix-web 4
- dicom 0.8
- Interface web moderne avec CSS Grid/Flexbox
