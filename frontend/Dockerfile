FROM node:20-alpine

WORKDIR /app

# Install dependencies first (layer cache-friendly)
COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 3000

# Hot-reload dev server; src and public are mounted as volumes in docker-compose
CMD ["npm", "run", "dev"]
