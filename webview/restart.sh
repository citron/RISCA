#!/bin/bash

echo "🔄 Redémarrage du serveur DICOM..."

# Kill any existing server on port 8104
PID=$(lsof -ti:8104 2>/dev/null)
if [ ! -z "$PID" ]; then
    echo "📛 Arrêt du serveur existant (PID: $PID)..."
    kill -9 $PID 2>/dev/null
    sleep 2
fi

# Start new server
cd /home/gacquewi/RISCA/webview
echo "🚀 Démarrage du nouveau serveur..."
nohup ./target/release/server > /tmp/dicom-server.log 2>&1 &

sleep 3

# Check if started
if lsof -ti:8104 > /dev/null 2>&1; then
    echo "✅ Serveur démarré sur http://localhost:8104"
    echo "📋 Logs: tail -f /tmp/dicom-server.log"
else
    echo "❌ Échec du démarrage. Vérifiez les logs:"
    cat /tmp/dicom-server.log
fi
