import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import API_CONFIG from '../config';

const Settings = ({ onLogout }) => {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Список городов
  const cities = useMemo(() => [
    'Балашиха', 'Железнодорожный', 'Жуковский', 'Ивантеевка', 'Казань',
    'Королев', 'Люберцы', 'Мытищи', 'Ногинск', 'Пушкино',
    'Раменское', 'Сергиев Посад', 'Фрязино', 'Щелково', 'Электросталь'
  ], []);

  const loadSettings = useCallback(async () => {
    try {
      const response = await axios.get(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.settings}`);
      const loadedSettings = response.data;
      
      // Инициализируем настройки для всех городов
      const initializedSettings = {};
      cities.forEach(city => {
        initializedSettings[city] = loadedSettings[city] || '';
      });
      
      setSettings(initializedSettings);
    } catch (err) {
      if (err.response && err.response.status === 404) {
        // Если настроек нет, создаем пустые
        const emptySettings = {};
        cities.forEach(city => {
          emptySettings[city] = '';
        });
        setSettings(emptySettings);
      } else {
        setError('Ошибка при загрузке настроек');
      }
    } finally {
      setLoading(false);
    }
  }, [cities]);

  useEffect(() => {
    // Настройка axios для отправки токена
    const token = localStorage.getItem('authToken');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    }
    
    loadSettings();
  }, [loadSettings]);

  const handleSettingChange = (city, value) => {
    setSettings(prev => ({
      ...prev,
      [city]: value
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      await axios.post(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.settings}`, settings, {
        headers: { 'Content-Type': 'application/json' }
      });
      setSuccess('Настройки сохранены успешно');
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Ошибка при сохранении настроек');
      }
    } finally {
      setSaving(false);
    }
  };

  const validateSettings = () => {
    const emptyCities = cities.filter(city => !settings[city] || settings[city].trim() === '');
    if (emptyCities.length > 0) {
      setError(`Следующие города не имеют ссылок: ${emptyCities.join(', ')}`);
      return false;
    }
    return true;
  };

  const handleSaveAndValidate = () => {
    if (validateSettings()) {
      handleSave();
    }
  };

  if (loading) {
    return (
      <div className="container">
        <div className="card">
          <p>Загрузка настроек...</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="header">
        <div className="header-content">
          <h1>Настройки</h1>
          <div className="header-buttons">
            <Link to="/" className="btn btn-secondary">
              Назад
            </Link>
            <button onClick={onLogout} className="btn btn-secondary">
              Выйти
            </button>
          </div>
        </div>
      </div>

      <div className="container">
        <div className="card">
          <h2>Настройки городов и ссылок</h2>
          
          {error && <div className="error">{error}</div>}
          {success && <div className="success">{success}</div>}
          
          <p>
            Укажите ссылки на Google таблицы для каждого города. 
            При обработке XLS файла данные будут записываться в соответствующие таблицы.
          </p>
          
          <table className="settings-table">
            <thead>
              <tr>
                <th>Город</th>
                <th>Ссылка на Google таблицу</th>
              </tr>
            </thead>
            <tbody>
              {cities.map(city => (
                <tr key={city}>
                  <td>{city}</td>
                  <td>
                    <input
                      type="url"
                      value={settings[city] || ''}
                      onChange={(e) => handleSettingChange(city, e.target.value)}
                      placeholder="https://docs.google.com/spreadsheets/d/..."
                      style={{ width: '100%' }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
            <button 
              onClick={handleSave} 
              className="btn"
              disabled={saving}
            >
              {saving ? 'Сохранение...' : 'Сохранить'}
            </button>
            
            <button 
              onClick={handleSaveAndValidate} 
              className="btn btn-secondary"
              disabled={saving}
            >
              {saving ? 'Сохранение...' : 'Сохранить и проверить'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings; 