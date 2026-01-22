#!/bin/bash

echo "Building DICOM Viewer..."

echo "Building server..."
cargo build --bin server --release

echo ""
echo "✅ Build complete!"
echo ""
echo "To start the server, run:"
echo "  ./target/release/server"
echo ""
echo "Then open http://localhost:8104 in your browser"
