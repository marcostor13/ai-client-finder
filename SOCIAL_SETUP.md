# Configuración de Redes Sociales — Video Editor

Guía completa para conectar YouTube, Instagram y TikTok al editor de video.

---

## Variables de entorno requeridas

Agrega estas líneas a tu archivo `.env` en la raíz del proyecto:

```env
# YouTube OAuth
YOUTUBE_CLIENT_ID=tu_client_id_aqui
YOUTUBE_CLIENT_SECRET=tu_client_secret_aqui

# URL base del backend (para el redirect de OAuth)
APP_BASE_URL=http://localhost:8000
```

Instagram y TikTok usan tokens pegados manualmente en la UI — no requieren variables en `.env`.

---

## YouTube

### Cómo funciona
El backend implementa OAuth 2.0 completo. El usuario hace clic en "Conectar YouTube" → es redirigido a Google → autoriza → regresa a la app con el token almacenado en MongoDB. Los uploads usan la YouTube Data API v3 con upload resumible.

### Pasos de configuración

**1. Crear proyecto en Google Cloud Console**
- Ve a [console.cloud.google.com](https://console.cloud.google.com)
- Crea un proyecto nuevo (ej. `video-editor-app`)

**2. Habilitar YouTube Data API v3**
- En el menú lateral: **APIs y servicios → Biblioteca**
- Busca `YouTube Data API v3`
- Haz clic en **Habilitar**

**3. Crear credenciales OAuth 2.0**
- Ve a **APIs y servicios → Credenciales**
- Clic en **+ Crear credenciales → ID de cliente de OAuth**
- Tipo de aplicación: **Aplicación web**
- Nombre: `Video Editor`
- En **URIs de redireccionamiento autorizados**, agrega:
  ```
  http://localhost:8000/video/social/youtube/callback
  ```
  > Si en producción el backend tiene otro dominio, agrega ese URI también.
- Clic en **Crear**
- Copia el **Client ID** y el **Client Secret**

**4. Agregar al `.env`**
```env
YOUTUBE_CLIENT_ID=123456789-abcdefgh.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxxxxx
APP_BASE_URL=http://localhost:8000
```

**5. Pantalla de consentimiento OAuth**
- Ve a **APIs y servicios → Pantalla de consentimiento de OAuth**
- Tipo de usuario: **Externo**
- Completa nombre de la app, email de soporte
- En **Scopes**, agrega:
  - `https://www.googleapis.com/auth/youtube.upload`
  - `https://www.googleapis.com/auth/youtube`
- En **Usuarios de prueba**, agrega tu email de Google/YouTube
  > Mientras la app esté en modo "Testing", solo los usuarios de prueba pueden conectarse.

**6. Conectar desde la app**
- En el Editor de Video → paso Publicar
- Clic en **Conectar YouTube**
- El backend redirige a Google → autoriza → regresa a `/video?connected=youtube`

### Límites y restricciones
| Aspecto | Detalle |
|---|---|
| Cuota diaria | 10,000 unidades/día (un upload = ~1,600 unidades) |
| Tamaño máximo | 256 GB o 12 horas |
| Formatos soportados | MP4, MOV, AVI, etc. |
| Modo Testing | Solo usuarios de prueba registrados pueden usar OAuth |
| Producción | Requiere verificación de Google si la app es pública |

---

## Instagram

### Cómo funciona
Instagram requiere una cuenta **Business o Creator** conectada a una página de Facebook. El sistema usa la Meta Graph API v19.0. El flujo es:
1. Crear un contenedor de media (video_url debe ser una URL pública — las presigned URLs de S3 funcionan)
2. Esperar que Instagram procese el video (~30-60 segundos)
3. Publicar el contenedor

El token se pega manualmente en la UI (botón "Conectar Instagram" → modal → pegar token).

### Pasos de configuración

**1. Requisitos previos**
- Cuenta de Instagram **Business** o **Creator** (no personal)
- Página de Facebook vinculada a esa cuenta de Instagram
- Cuenta en [developers.facebook.com](https://developers.facebook.com)

**2. Crear app en Meta for Developers**
- Ve a [developers.facebook.com/apps](https://developers.facebook.com/apps)
- Clic en **Crear app**
- Tipo: **Business** (o "Otro" → Business)
- Completa nombre y email de contacto

**3. Agregar Instagram Graph API**
- En el dashboard de tu app, ve a **Agregar productos**
- Busca **Instagram Graph API** → clic en **Configurar**

**4. Obtener un token de acceso de larga duración**

Hay dos métodos:

**Método A — Graph API Explorer (más rápido para pruebas):**
- Ve a [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer)
- Selecciona tu app en el desplegable
- Clic en **Generar token de acceso**
- Marca los permisos:
  - `instagram_basic`
  - `instagram_content_publish`
  - `pages_read_engagement`
- Copia el token generado

**Método B — Token de larga duración (recomendado, dura 60 días):**
```
GET https://graph.facebook.com/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={app_id}
  &client_secret={app_secret}
  &fb_exchange_token={token_corto}
```
Llama a este endpoint con tu token corto para obtener uno que dura 60 días.

**5. Conectar desde la app**
- Editor de Video → Publicar → tarjeta Instagram → **Conectar Instagram**
- Pega el token de acceso en el modal
- El backend valida el token llamando a `/me` en Graph API y guarda el `instagram_user_id`

**6. Publicar**
- Selecciona el formato: **Reels** (9:16, máx 90s), **Stories** (9:16, máx 60s) o **Feed** (1:1, máx 60s)
- Escribe caption y clic en Publicar
- El video debe pesar menos de 1 GB y durar entre 3 y 90 segundos para Reels

### Límites y restricciones
| Aspecto | Detalle |
|---|---|
| Token de corta duración | Expira en 1 hora |
| Token de larga duración | Expira en 60 días (renovable) |
| Requiere | Cuenta Business/Creator + Página de Facebook |
| Reels duración | 3 segundos – 90 segundos |
| Tamaño máximo | 1 GB |
| Cuota API | 200 llamadas/hora por usuario |
| URL del video | Debe ser pública (las presigned URLs de S3 funcionan) |

> **Importante:** Los videos en S3 deben ser accesibles públicamente o mediante presigned URL. Las presigned URLs de AWS duran 24 horas — suficiente para el proceso de publicación.

---

## TikTok

### Cómo funciona
TikTok usa el Content Posting API v2. El token se pega manualmente. El flujo es: init upload → PUT del archivo en chunks → TikTok procesa y publica.

> **Advertencia:** El Content Posting API de TikTok requiere aprobación del equipo de TikTok para developers. No es de acceso inmediato.

### Pasos de configuración

**1. Crear cuenta de desarrollador**
- Ve a [developers.tiktok.com](https://developers.tiktok.com)
- Regístrate con tu cuenta de TikTok
- Crea una app en el portal

**2. Solicitar acceso al Content Posting API**
- En tu app, ve a **Manage** → **Products** → busca **Content Posting API**
- Solicita acceso (requiere revisión de TikTok — puede tomar días/semanas)
- Necesitarás justificar el uso: "publicación de videos editados desde herramienta interna"

**3. Obtener Access Token**
Una vez aprobada la app:
- Implementa el flujo OAuth de TikTok para obtener el `access_token` con scope `video.publish`
- O usa el **Sandbox** de TikTok para pruebas (el portal tiene un generador de tokens de sandbox)

**4. Conectar desde la app**
- Editor de Video → Publicar → tarjeta TikTok → **Conectar TikTok**
- Pega el `access_token` en el modal

### Scopes requeridos
```
video.publish       — para subir videos
video.upload        — para el proceso de upload en chunks
user.info.basic     — para verificar la cuenta
```

### Límites y restricciones
| Aspecto | Detalle |
|---|---|
| Acceso | Requiere aprobación previa de TikTok |
| Token | Expira en 24 horas (renovable con refresh_token) |
| Tamaño máximo | 4 GB |
| Duración | 1 segundo – 10 minutos |
| Cuota | 100 uploads/día por app |
| Sandbox | Disponible para pruebas sin publicación real |

---

## Flujo completo de conexión en la app

```
Editor de Video
└── Paso 5: Publicar
    ├── YouTube    → [Conectar] → redirige a Google OAuth → retorna automáticamente
    ├── Instagram  → [Conectar] → modal → pegar token manualmente → guardar
    └── TikTok     → [Conectar] → modal → pegar token manualmente → guardar

Al publicar:
    ├── YouTube    → descarga el MP4 de S3 a temp → upload resumible a YouTube API
    ├── Instagram  → pasa la presigned URL de S3 a Meta Graph API (sin descarga local)
    └── TikTok     → descarga el MP4 de S3 a temp → PUT en chunks a TikTok API
```

---

## Checklist de `.env` completo para video + social

```env
# AWS S3 (videos)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=nombre-de-tu-bucket
S3_REGION=us-east-1

# YouTube OAuth
YOUTUBE_CLIENT_ID=....apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=GOCSPX-...
APP_BASE_URL=http://localhost:8000
```

---

## Solución de problemas comunes

| Error | Causa | Solución |
|---|---|---|
| `YouTube OAuth not configured` | Faltan variables en .env | Agrega `YOUTUBE_CLIENT_ID` y `YOUTUBE_CLIENT_SECRET` |
| `Invalid redirect_uri` en Google | URI no registrado | Agrega `http://localhost:8000/video/social/youtube/callback` en Google Console |
| `Invalid Instagram token` | Token expirado o sin permisos | Regenera con `instagram_content_publish` habilitado |
| `Instagram user ID not found` | Token válido pero sin Página de Facebook | Vincula tu cuenta IG a una Página de Facebook |
| `TikTok 401 Unauthorized` | Token expirado | Regenera el access token en el portal de TikTok |
| `TikTok API not accessible` | App no aprobada | Solicitar acceso al Content Posting API y esperar aprobación |
| `S3 presigned URL expired` | URL de más de 24h | Usa el botón "Refrescar URLs" en el historial de jobs |
