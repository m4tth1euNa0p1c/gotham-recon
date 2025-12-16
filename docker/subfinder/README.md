# Subfinder Docker Service

Ce dossier contient la configuration pour construire l'image Docker de **Subfinder**.

## Installation

Pour que l'agent puisse utiliser ce service, vous devez construire l'image avec le tag `gotham/subfinder` :

```powershell
docker build -t gotham/subfinder .
```

## Test

Une fois construit, vous pouvez tester que cela fonctionne :

```powershell
docker run --rm gotham/subfinder -version
```
