import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const Dashboard = ({ onLogout }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Список городов
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

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && (file.type === 'application/vnd.ms-excel' || 
                 file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                 file.name.endsWith('.xls') || file.name.endsWith('.xlsx'))) {
      setSelectedFile(file);
      setError('');
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
    setSuccess('');
    setUploadStatus('Идет загрузка файла...');
    setProcessingStatus(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setUploadStatus('Файл загружен успешно');
      setSuccess('Скрипт выполнен');
      
      // Начинаем отслеживать статус обработки
      if (response.data.task_id) {
        trackProcessingStatus(response.data.task_id);
      }
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Ошибка при загрузке файла');
      }
      setUploadStatus('Ошибка загрузки');
    } finally {
      setUploading(false);
    }
  };

  const trackProcessingStatus = async (taskId) => {
    const checkStatus = async () => {
      try {
        const response = await axios.get(`/api/status/${taskId}`);
        const status = response.data;
        
        setProcessingStatus(status);
        
        if (status.status === 'completed' || status.status === 'failed') {
          return; // Останавливаем проверку
        }
        
        // Проверяем снова через 2 секунды
        setTimeout(checkStatus, 2000);
      } catch (err) {
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
          {success && <div className="success">{success}</div>}
          
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

        {(uploadStatus || processingStatus) && (
          <div className="card">
            <h2>Вывод</h2>
            
            {processingStatus && (
              <div>
                {processingStatus.status === 'failed' && processingStatus.error && (
                  <div className="error" style={{ marginTop: '10px' }}>
                    <strong>Ошибка:</strong> {processingStatus.error}
                  </div>
                )}
                
                {processingStatus.errors && processingStatus.errors.length > 0 && (
                  <div className="status-list">
                    <h4>Ошибки:</h4>
                    {processingStatus.errors.map((error, index) => (
                      <div key={index} className="status-item status-error">
                        <span>{error.city}</span>
                        <span>{error.message}</span>
                      </div>
                    ))}
                  </div>
                )}
                
                {processingStatus.success && processingStatus.success.length > 0 && (
                  <div className="status-list">
                    <h4>Успешно обработано:</h4>
                    {processingStatus.success.map((city, index) => (
                      <div key={index} className="status-item status-success">
                        <span>{city}</span>
                        <span>✅</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard; 