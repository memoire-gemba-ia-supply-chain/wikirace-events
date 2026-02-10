#!/bin/bash
# Script de déploiement pour WikiRace Event Scraper
# Ce script configure le repository GitHub pour l'automatisation

set -e

echo "🏃 WikiRace Scraper - Déploiement GitHub"
echo "=========================================="

# Configuration
REPO_NAME="wikirace-events"
BRANCH="main"

# Vérifier si on est dans un repo git
if [ ! -d ".git" ]; then
    echo "❌ Ce dossier n'est pas un repository git"
    echo "   Initialisation..."
    git init
    git branch -M main
fi

# Vérifier la configuration git
if [ -z "$(git config user.email)" ]; then
    echo "⚠️  Veuillez configurer votre email git:"
    echo "   git config user.email 'votre@email.com'"
    exit 1
fi

# Créer .gitignore si nécessaire
if [ ! -f ".gitignore" ]; then
    echo "📝 Création du .gitignore..."
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
.env

# IDE
.idea/
.vscode/
*.swp
*.swo

# macOS
.DS_Store
*.dSYM/

# iOS/Xcode
*.xcuserstate
xcuserdata/
DerivedData/
build/
*.ipa
*.xcarchive/

# Logs
*.log
EOF
fi

# Ajouter les fichiers
echo "📦 Ajout des fichiers..."
git add .github/
git add scraper/
git add events.json
git add .gitignore

# Commit
echo "💾 Commit des changements..."
git commit -m "🚀 Setup automated event scraping

- Add GitHub Actions workflow for daily scraping
- Configure RunSignup, ITRA, UltraSignup sources
- Auto-update events.json daily at 6:00 UTC"

echo ""
echo "✅ Repository local prêt!"
echo ""
echo "📋 Prochaines étapes:"
echo ""
echo "1. Créez un nouveau repository sur GitHub:"
echo "   https://github.com/new"
echo "   Nom: $REPO_NAME"
echo ""
echo "2. Liez et poussez le repository:"
echo "   git remote add origin https://github.com/VOTRE_USERNAME/$REPO_NAME.git"
echo "   git push -u origin main"
echo ""
echo "3. Après le push, l'URL publique de vos données sera:"
echo "   https://raw.githubusercontent.com/VOTRE_USERNAME/$REPO_NAME/main/events.json"
echo ""
echo "4. Le scraping automatique s'exécutera tous les jours à 6h UTC"
echo "   Vous pouvez aussi le déclencher manuellement dans l'onglet 'Actions'"
echo ""
