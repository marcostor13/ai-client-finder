# Despliegue — AI Client Finder

Frontend en **Netlify** · Backend en **Coolify** (Docker) · DB en **MongoDB Atlas** (ya existe).

```
[ Navegador ]
     │  https
     ▼
[ Netlify ]  ──VITE_API_URL──►  [ Coolify / Docker ]  ──►  [ MongoDB Atlas ]
  React+Vite                      FastAPI + Playwright          (ya en la nube)
                                  + ffmpeg
```

---

## 0. Antes de empezar (IMPORTANTE — seguridad)

El archivo `.env` actual tiene **claves reales** (OpenAI, Claude, AWS, SMTP, Mongo…).
Ya está en `.gitignore`, así que no se subirá. Pero como estuvieron en texto plano,
**conviene rotar** las que sean sensibles (sobre todo AWS y la contraseña de Mongo)
antes de exponer el backend públicamente.

Las variables se cargan en Coolify desde su panel; **no** se sube ningún `.env`.

---

## 1. Subir el código a Git

Netlify y Coolify despliegan desde un repositorio. Aún no hay git inicializado.

```bash
cd "c:/Marcos/Proyectos/Clientes/ai-client-finder"
git init
git add .
git commit -m "Preparar despliegue Netlify + Coolify"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/ai-client-finder.git
git push -u origin main
```

Verifica que **`.env` NO aparece** en `git status` antes del commit.

---

## 2. Backend → Coolify

El backend necesita Chromium (Playwright) y ffmpeg, por eso usa **Dockerfile**
(no Nixpacks). Coolify lo detecta automáticamente.

1. **New Resource → Application** → conecta tu repo de GitHub.
2. **Build Pack: Dockerfile.** Dockerfile path: `./Dockerfile` · Build context: `/` (raíz).
3. **Port expuesto: `8000`.**
4. **Environment Variables**: copia todas las de `.env.example` con sus valores reales.
   Imprescindibles: `MONGODB_URL`, `DATABASE_NAME`, `JWT_SECRET`, `OPENAI_API_KEY`,
   `CLAUDE_API_KEY`, y `CORS_ORIGINS` = la URL de tu sitio Netlify.
5. **Dominio**: asigna uno (p. ej. `https://api.tudominio.com`). Coolify gestiona el SSL.
6. **Health check** (opcional): path `/` (responde `{"message": "...running"}`).
7. Deploy.

Notas:
- **1 solo worker** (ya configurado en el Dockerfile): el scheduler `apscheduler`
  corre en proceso; con varios workers los jobs se duplicarían. Para escalar,
  habría que mover el scheduler a un proceso/servicio aparte.
- La primera build tarda (descarga Chromium + deps). Builds siguientes usan caché.
- MongoDB Atlas: en **Network Access** permite la IP saliente de tu servidor Coolify
  (o `0.0.0.0/0` si usas usuario/contraseña fuertes).

### Crear el usuario admin (una vez)
Tras el primer deploy, abre una terminal en el contenedor (Coolify → Terminal) y:
```bash
python -m backend.scripts.create_admin
```

---

## 3. Frontend → Netlify

1. **Add new site → Import from Git** → mismo repo.
2. Netlify lee `netlify.toml` (ya incluido): base `frontend`, build `npm ci && npm run build`,
   publish `frontend/dist`, con fallback SPA. No hay que configurar nada a mano.
3. **Site settings → Environment variables**:
   - `VITE_API_URL` = URL del backend en Coolify (p. ej. `https://api.tudominio.com`, sin `/` final).
4. Deploy.

⚠️ Vite **incrusta** `VITE_API_URL` en build. Si la cambias luego, hay que **redesplegar**.

---

## 4. Conectar ambos (orden recomendado)

1. Despliega primero el **backend** y anota su URL pública.
2. En Netlify pon esa URL en `VITE_API_URL` y despliega el **frontend**.
3. Copia la URL final de Netlify a `CORS_ORIGINS` en Coolify y redespliega el backend.
4. Entra al sitio Netlify, login con el admin, y prueba una búsqueda.

---

## 5. Desarrollo local (sigue funcionando igual)

```bash
# Backend (desde la raíz del proyecto)
uvicorn backend.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```
Sin `VITE_API_URL`, el frontend usa `http://localhost:8000` por defecto.

---

## Checklist de archivos añadidos
- `Dockerfile` · `.dockerignore` — imagen del backend (Coolify)
- `netlify.toml` · `frontend/public/_redirects` — build + SPA (Netlify)
- `.gitignore` — protege `.env`, `.venv`, `node_modules`, `dist`
- `.env.example` · `frontend/.env.example` — plantillas de variables
- Cambios: `frontend/src/api.js` (URL por env), `backend/main.py` (CORS por env),
  `backend/requirements.txt` (`uvicorn[standard]`)

<!-- auto-deploy webhook test: 2026-06-22 -->
