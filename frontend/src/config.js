// Конфигурация API
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const API_CONFIG = {
  baseURL: API_BASE_URL,
  endpoints: {
    login: '/api/login',
    upload: '/api/upload',
    status: '/api/status',
    settings: '/api/settings'
  }
};

export default API_CONFIG; 