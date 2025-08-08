import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import API_CONFIG from '../config';
import './Dashboard.css';

const Dashboard = ({ onLogout }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [error, setError] = useState('');
  const [logTimes, setLogTimes] = useState({});
  const [lastSuccessCount, setLastSuccessCount] = useState(0);
  const [lastErrorsCount, setLastErrorsCount] = useState(0);

  // Список городов (используется в других компонентах)
  // eslint-disable-next-line no-unused-vars
  const cities = [
    'Балашиха', 'Железнодорожный', 'Жуковский', 'Ивантеевка', 'Казань',
    'Королев', 'Люберцы', 'Мытищи', 'Ногинск', 'Пушкино',
    'Раменское', 'Сергиев Посад', 'Фрязино', 'Щелково', 'Электросталь'
  ];

  useEffect(() => {
    // Настройка axios для отправки токена
    const token = localStorage.getItem('authToken');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    }
  }, []);

  // useEffect для обработки времени логов
  useEffect(() => {
    if (processingStatus && processingStatus.success) {
      const currentSuccessCount = processingStatus.success.length;
      
              if (currentSuccessCount > lastSuccessCount) {
          setLogTimes(prevLogTimes => {
            const newLogTimes = { ...prevLogTimes };
            
            // Добавляем время только для новых логов
            processingStatus.success.slice(lastSuccessCount).forEach((log, index) => {
              const actualIndex = lastSuccessCount + index;
              const logKey = `success-${actualIndex}-${log}`;
              newLogTimes[logKey] = new Date().toLocaleTimeString();
            });
            return newLogTimes;
          });
          setLastSuccessCount(currentSuccessCount);
        }
    }
    
    if (processingStatus && processingStatus.errors) {
      const currentErrorsCount = processingStatus.errors.length;
      
      if (currentErrorsCount > lastErrorsCount) {
        setLogTimes(prevLogTimes => {
          const newLogTimes = { ...prevLogTimes };
          
          // Добавляем время только для новых ошибок
          processingStatus.errors.slice(lastErrorsCount).forEach((error, index) => {
            const actualIndex = lastErrorsCount + index;
            const logKey = `error-${actualIndex}-${error.city}-${error.message}`;
            newLogTimes[logKey] = new Date().toLocaleTimeString();
          });
          return newLogTimes;
        });
        setLastErrorsCount(currentErrorsCount);
      }
    }
  }, [processingStatus, lastSuccessCount, lastErrorsCount]);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && (file.type === 'application/vnd.ms-excel' || 
                 file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                 file.name.endsWith('.xls') || file.name.endsWith('.xlsx'))) {
      setSelectedFile(file);
      setError('');
      // Очищаем старый статус обработки при выборе нового файла
      setProcessingStatus(null);
    } else {
      setError('Пожалуйста, выберите файл формата .xls или .xlsx');
      setSelectedFile(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && (file.type === 'application/vnd.ms-excel' || 
                 file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                 file.name.endsWith('.xls') || file.name.endsWith('.xlsx'))) {
      setSelectedFile(file);
      setError('');
      // Очищаем старый статус обработки при выборе нового файла
      setProcessingStatus(null);
    } else {
      setError('Пожалуйста, выберите файл формата .xls или .xlsx');
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const uploadFile = async () => {
    if (!selectedFile) {
      setError('Пожалуйста, выберите файл');
      return;
    }

    setUploading(true);
    setError('');
    setUploadStatus('Идет загрузка файла...');
    
    // Создаем начальный статус для отображения блока прогресса
    setProcessingStatus({
      status: 'processing',
      progress: { current: 0, total: 15 },
      errors: [],
      success: ['Загрузка файла...']
    });
    
    // Сбрасываем счетчики для новой обработки
    setLastSuccessCount(0);
    setLastErrorsCount(0);
    setLogTimes({});

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {

      
      const response = await axios.post(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.upload}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000, // 2 минуты таймаут для больших файлов
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadStatus(`Загрузка файла... ${percentCompleted}%`);
        },
      });
      
      setUploadStatus('Файл загружен успешно');
      
      // Начинаем отслеживать статус обработки
      if (response.data && response.data.task_id) {
        localStorage.setItem('lastTaskId', response.data.task_id);
        trackProcessingStatus(response.data.task_id);
      } else {
        // Пробуем получить последний task_id из localStorage
        const lastTaskId = localStorage.getItem('lastTaskId');
        if (lastTaskId) {
          trackProcessingStatus(lastTaskId);
        } else {
          setError('Ошибка: не получен ID задачи от сервера');
        }
      }
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Ошибка при загрузке файла');
      }
      setUploadStatus('Ошибка загрузки');
      setProcessingStatus(null);
    } finally {
      setUploading(false);
    }
  };

  const trackProcessingStatus = async (taskId) => {
    const checkStatus = async () => {
      try {
        const response = await axios.get(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.status}/${taskId}`, {
          timeout: 30000, // 30 секунд таймаут
        });
        
        const status = response.data;

        
        // Обновляем статус
        setProcessingStatus(status);
        
        // Останавливаем опрос статуса при завершении обработки всех 15 городов
        if (status.status === 'completed' || status.status === 'failed') {
          return; // Останавливаем проверку
        }
        
        // Также останавливаем, если прогресс достиг максимума (15 городов)
        if (status.progress && status.progress.current >= status.progress.total) {
          return; // Останавливаем проверку
        }
        
        // Продолжаем опрашивать каждые 500мс
        const interval = status.status === 'processing' && status.progress?.current === 0 ? 300 : 500;
        setTimeout(checkStatus, interval);
      } catch (err) {
        // При ошибке таймаута продолжаем опрашивать
        if (err.code === 'ECONNABORTED' || err.message.includes('timeout')) {
          setTimeout(checkStatus, 2000);
          return;
        }
        
        setError('Ошибка при получении статуса обработки');
      }
    };
    
    checkStatus();
  };

  return (
    <div>
      <div className="header">
        <div className="header-content">
          <h1>Два гостя</h1>
          <div className="header-buttons">
            <Link to="/settings" className="btn btn-secondary">
              Настройки
            </Link>
            <button onClick={onLogout} className="btn btn-secondary">
              Выйти
            </button>
          </div>
        </div>
      </div>

      <div className="container">
        <div className="card">
          <h2>Загрузка файла</h2>
          
          {error && <div className="error">{error}</div>}
          
          <div 
            className="file-upload-area"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => document.getElementById('file-input').click()}
          >
            <div className="upload-icon">📁</div>
                         <p>Перетащите файл Excel (.xls или .xlsx) сюда или нажмите для выбора</p>
                         <input
               id="file-input"
               type="file"
               accept=".xls,.xlsx"
               onChange={handleFileSelect}
             />
          </div>
          
          {selectedFile && (
            <div style={{ marginTop: '15px' }}>
              <p><strong>Выбранный файл:</strong> {selectedFile.name}</p>
              <button 
                onClick={uploadFile} 
                className="btn" 
                disabled={uploading}
              >
                {uploading ? 'Загрузка...' : 'Загрузить и обработать'}
              </button>
              

            </div>
          )}
        </div>

        {/* Блок прогресса в реальном времени */}
        {processingStatus && (
          <div className="card">

            <div className="realtime-logs">
              {processingStatus.progress && processingStatus.status === 'processing' && (
                <div className="progress-info">
                  <div className="progress-header">
                    <span className="progress-text">
                      {processingStatus.progress.current}/{processingStatus.progress.total} 
                      {processingStatus.progress.current_city && (
                        <span className="current-city"> - {processingStatus.progress.current_city}</span>
                      )}
                    </span>
                    <span className="progress-percentage">
                      {Math.round((processingStatus.progress.current / processingStatus.progress.total) * 100)}%
                    </span>
                  </div>
                  <div className="progress-bar">
                    <div 
                      className="progress-fill"
                      style={{ 
                        width: `${(processingStatus.progress.current / processingStatus.progress.total) * 100}%` 
                      }}
                    ></div>
                  </div>
                </div>
              )}
              
              <div className="logs-container">
                <div className="logs-list">
                  {processingStatus.success && processingStatus.success.length > 0 ? (
                    processingStatus.success.map((log, index) => {
                      const timeKey = `success-${index}-${log}`;
                      const time = logTimes[timeKey] || '--:--:--';

                      return (
                        <div key={index} className="log-item success">
                          <span className="log-time">{time}</span>
                          <span className="log-message">{log}</span>
                        </div>
                      );
                    })
                  ) : (
                    <div className="log-item">
                      <span className="log-time">{new Date().toLocaleTimeString()}</span>
                      <span className="log-message">Ожидание начала обработки...</span>
                    </div>
                  )}
                  {processingStatus.errors && processingStatus.errors.map((error, index) => (
                    <div key={index} className="log-item error">
                      <span className="log-time">{logTimes[`error-${index}-${error.city}-${error.message}`] || '--:--:--'}</span>
                      <span className="log-message">{error.city}: {error.message}</span>
                    </div>
                  ))}
                  
                  {processingStatus.status === 'failed' && processingStatus.error && (
                    <div className="log-item error">
                      <span className="log-time">{new Date().toLocaleTimeString()}</span>
                      <span className="log-message">Критическая ошибка: {processingStatus.error}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}


      </div>
    </div>
  );
};

export default Dashboard; 