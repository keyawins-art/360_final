import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const API_URL = 'http://127.0.0.1:8000/api';

function App() {
  const [status, setStatus] = useState('System Ready');
  const [activeCount, setActiveCount] = useState(0);
  const [currentMode, setCurrentMode] = useState('Stopped');
  const [activePage, setActivePage] = useState('Control Hub');
  const [graphData, setGraphData] = useState([]);
  const [currentDateTime, setCurrentDateTime] = useState(new Date());

  // Pagination state for Air Valve
  const [airValvePage, setAirValvePage] = useState(1);

  // Main Settings Page State
  const [mainSettingsValue, setMainSettingsValue] = useState("");
  const [showMainSettingsNumpad, setShowMainSettingsNumpad] = useState(false);
  const [showBeltsGrid, setShowBeltsGrid] = useState(true);
  const [mainSettingsSelectedBelt, setMainSettingsSelectedBelt] = useState(null);

  // Custom Confirmation Dialog State
  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, type: null, title: '', message: '' });

  // Login Modal State
  const [showLogin, setShowLogin] = useState(false);
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState(false);
  const [pendingPage, setPendingPage] = useState(null);

  // Toast Notification State
  const [toast, setToast] = useState({ show: false, message: '', type: 'success' });
  const showToast = (message, type = 'success') => {
    setToast({ show: true, message, type });
    setTimeout(() => {
      setToast(t => ({ ...t, show: false }));
    }, 4000);
  };

  // Customization State
  const [activeInput, setActiveInput] = useState(null); // { level: '400', field: 'min' }
  const defaultCustoms = {
    '400': { min: '', max: '' },
    '320': { min: '', max: '' },
    '240': { min: '', max: '' },
    '210': { min: '', max: '' },
    '180': { min: '', max: '' }
  };
  const [customValues, setCustomValues] = useState(defaultCustoms);
  const [savedCustomValues, setSavedCustomValues] = useState(defaultCustoms);

  // Time Setting State
  const [timeSettingsValues, setTimeSettingsValues] = useState(() => {
    const defaultSettings = {};
    for (let i = 1; i <= 15; i++) {
      defaultSettings[i.toString()] = ["", "", "", "", "", "", ""];
    }
    return defaultSettings;
  });

  const [activeSettingsModule, setActiveSettingsModule] = useState(null);
  const [activeTimeInput, setActiveTimeInput] = useState(null); // { belt: "1", idx: 0 }

  // Camera Settings State
  const defaultCameraParams = {
    exposure: 50000,
    gain: 0,
    width: 1440,
    height: 1080,
    offsetX: 0,
    offsetY: 0
  };
  const [cameraParams, setCameraParams] = useState({
    "1": { ...defaultCameraParams },
    "2": { ...defaultCameraParams },
    "3": { ...defaultCameraParams }
  });
  const [activeCamParamIdx, setActiveCamParamIdx] = useState("1");
  
  // Zones Configuration State
  const [zonesTab, setZonesTab] = useState('camera'); // 'camera' or 'zones'
  const [zones, setZones] = useState([
    {"name": "Zone-1", "zone": [100, 100, 370, 1920]},
    {"name": "Zone-2", "zone": [540, 100, 350, 1910]},
    {"name": "Zone-3", "zone": [960, 100, 360, 1910]},
    {"name": "Zone-4", "zone": [1400, 100, 340, 1910]},
    {"name": "Zone-5", "zone": [1840, 100, 370, 1910]}
  ]);
  const [activeZoneIdx, setActiveZoneIdx] = useState(0);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [cameraRefs, setCameraRefs] = useState(["", "", ""]);
  const [connectedCameras, setConnectedCameras] = useState([]);
  const [isCheckingCameras, setIsCheckingCameras] = useState(false);

  // Comports Settings State
  const [comportRefs, setComportRefs] = useState(["", "", ""]);
  const [connectedComports, setConnectedComports] = useState([]);
  const [isCheckingComports, setIsCheckingComports] = useState(false);

  const closeConfirm = () => setConfirmDialog({ isOpen: false, type: null, title: '', message: '' });

  const handleConfirmAction = () => {
    if (confirmDialog.type === 'Shutdown') {
      handleAction('shutdown-device', 'System Shutdown');
    } else if (confirmDialog.type === 'Restart') {
      handleAction('restart-device', 'System Restart');
    }
    closeConfirm();
  };

  const toggleFullScreen = () => {
    const elem = document.getElementById('camera-feed-container');
    if (elem) {
      if (!document.fullscreenElement) {
        elem.requestFullscreen().catch(err => {
          console.error(`Error attempting to enable full-screen mode: ${err.message}`);
        });
      } else {
        document.exitFullscreen();
      }
    }
  };

  useEffect(() => {
    const timer = setInterval(() => setCurrentDateTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const navItems = [
    { name: 'Control Hub', type: 'page', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
    { name: 'Camera Setting', type: 'page', icon: 'M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z' },
    { name: 'Customizations', type: 'page', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z' },
    { name: 'Air Valve', type: 'page', icon: 'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z' },
    { name: 'Settings', type: 'page', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' },
    { name: 'Team Viewer', type: 'page', icon: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
    { name: 'Wi-Fi Connect', type: 'page', icon: 'M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.142 0M1.121 10.121a15.42 15.42 0 0121.758 0' },
    { name: 'Shutdown', type: 'action', color: 'red', icon: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z' },
    { name: 'Restart', type: 'action', color: 'orange', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15' }
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      axios.get(`${API_URL}/status`)
        .then(res => {
          setActiveCount(res.data.active_processes);
          if (res.data.current_mode) setCurrentMode(res.data.current_mode);
        })
        .catch(err => { /* Silent catch */ });

      axios.get(`${API_URL}/graph-data`)
        .then(res => {
          const data = res.data;
          const formatted = [
            { name: "400", count: data["400"] || 0, color: "#10b981" },
            { name: "320", count: data["320"] || 0, color: "#3b82f6" },
            { name: "240", count: data["240"] || 0, color: "#8b5cf6" },
            { name: "210", count: data["210"] || 0, color: "#ec4899" },
            { name: "180", count: data["180"] || 0, color: "#f59e0b" },
          ];
          setGraphData(formatted);
        })
        .catch(err => { /* Silent catch */ });
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Fetch customizations when entering page
  useEffect(() => {
    if (activePage === 'Customizations') {
      axios.get(`${API_URL}/customizations`)
        .then(res => {
          if (res.data && Object.keys(res.data).length > 0) {
            setCustomValues(prev => ({ ...prev, ...res.data }));
            setSavedCustomValues(prev => ({ ...prev, ...res.data }));
          }
        })
        .catch(err => console.error(err));
    }
  }, [activePage]);

  useEffect(() => {
    if (activePage === 'Time Setting') {
      axios.get(`${API_URL}/time-settings-all`)
        .then(res => {
          if (res.data && res.data.all_values) {
            setTimeSettingsValues(prev => ({ ...prev, ...res.data.all_values }));
          }
        })
        .catch(err => console.error(err));
    }
  }, [activePage]);

  const saveTimeSettings = async () => {
    try {
      await axios.post(`${API_URL}/time-settings-all`, { belts: timeSettingsValues });
      showToast(`All Belt Time Settings Saved!`);
    } catch (err) {
      console.error(err);
      showToast("Failed to save time settings.", "error");
    }
  };

  useEffect(() => {
    if (activePage === 'Camera Setting') {
      axios.get(`${API_URL}/camera-ref`)
        .then(res => {
          if (res.data && res.data.references) {
            setCameraRefs(res.data.references);
          }
        })
        .catch(err => console.error(err));

      axios.get(`${API_URL}/camera-params`)
        .then(res => {
          if (res.data && Object.keys(res.data).length > 0) {
            setCameraParams(prev => ({ ...prev, ...res.data }));
          }
        })
        .catch(err => console.error(err));

      axios.get(`${API_URL}/zones`)
        .then(res => {
          if (res.data && Array.isArray(res.data)) {
            setZones(res.data);
          }
        })
        .catch(err => console.error("Error fetching zones:", err));

      checkCameras();
    }
  }, [activePage]);

  const saveCameraParamsData = async () => {
    try {
      await axios.post(`${API_URL}/camera-params`, { params: cameraParams });
      showToast("Camera Parameters Saved Successfully!");
    } catch (err) {
      console.error(err);
      showToast("Failed to save camera parameters.", "error");
    }
  };

  const updateCameraParam = (field, value) => {
    setCameraParams(prev => ({
      ...prev,
      [activeCamParamIdx]: {
        ...prev[activeCamParamIdx],
        [field]: Number(value)
      }
    }));
  };

  useEffect(() => {
    if (Object.keys(cameraParams).length > 0 && activePage === 'Camera Setting') {
      const delayDebounceFn = setTimeout(() => {
        axios.post(`${API_URL}/camera-params`, { params: cameraParams })
          .catch(err => console.error("Auto-save error:", err));
      }, 150);
      return () => clearTimeout(delayDebounceFn);
    }
  }, [cameraParams, activePage]);

  const saveZonesConfig = () => {
    axios.post(`${API_URL}/zones`, zones)
      .then(() => showToast('Zones saved to zones_config.json!'))
      .catch(err => {
        console.error('Zones save error:', err);
        showToast('Failed to save zones!', 'error');
      });
  };

  const updateZoneParam = (idx, paramIdx, value) => {
    setZones(prev => {
      const updated = [...prev];
      if (updated[idx] && updated[idx].zone) {
        const zoneCoords = [...updated[idx].zone];
        zoneCoords[paramIdx] = Number(value);
        updated[idx] = { ...updated[idx], zone: zoneCoords };
      }
      return updated;
    });
  };

  const checkCameras = () => {
    setIsCheckingCameras(true);
    axios.get(`${API_URL}/camera-check`)
      .then(res => {
        if (res.data && res.data.cameras) {
          setConnectedCameras(res.data.cameras);
        }
      })
      .catch(err => console.error(err))
      .finally(() => setIsCheckingCameras(false));
  };

  const saveCameraRefs = async () => {
    try {
      await axios.post(`${API_URL}/camera-ref`, { references: cameraRefs });
      showToast("Camera references saved successfully!");
    } catch (err) {
      console.error(err);
      showToast("Failed to save camera references.", "error");
    }
  };

  const checkComports = () => {
    setIsCheckingComports(true);
    axios.get(`${API_URL}/comport-check`)
      .then(res => {
        if (res.data && res.data.comports) {
          setConnectedComports(res.data.comports);
        }
      })
      .catch(err => {
        console.error(err);
        setConnectedComports(["COM1", "COM2", "COM3", "COM4"]);
      })
      .finally(() => setIsCheckingComports(false));
  };

  const saveComportRefs = async () => {
    try {
      await axios.post(`${API_URL}/comport-ref`, { references: comportRefs });
      showToast("Comport references saved successfully!");
    } catch (err) {
      console.error(err);
      showToast("Failed to save comport references.", "error");
    }
  };

  const applyToAllBelts = () => {
    const belt1Values = timeSettingsValues["1"];
    setTimeSettingsValues(prev => {
      const newSettings = { ...prev };
      for (let i = 1; i <= 15; i++) {
        newSettings[i.toString()] = [...belt1Values];
      }
      return newSettings;
    });
    showToast("Belt 1 settings copied to all belts! Click 'Save' to confirm.", "info");
  };

  const handleTimeNumberClick = (num) => {
    if (!activeTimeInput) return;
    const { belt, idx } = activeTimeInput;
    setTimeSettingsValues(prev => {
      const newSettings = { ...prev };
      const beltVals = [...(newSettings[belt] || ["", "", "", "", "", "", ""])];
      if (num === 'DEL') {
        beltVals[idx] = beltVals[idx].slice(0, -1);
      } else {
        if (beltVals[idx].length >= 4) {
          beltVals[idx] = num.toString();
        } else {
          beltVals[idx] += num;
        }
      }
      newSettings[belt] = beltVals;
      return newSettings;
    });
  };

  const saveMainSettingsToBelt = async (beltNum) => {
    setMainSettingsSelectedBelt(beltNum);
    if (!mainSettingsValue) {
      showToast("Please enter a value first!", "error");
      return;
    }
    try {
      await axios.post(`${API_URL}/main-settings`, { 
        value: mainSettingsValue, 
        belt_number: beltNum 
      });
      showToast(`Value ${mainSettingsValue} saved to Belt ${beltNum} successfully!`);
    } catch (err) {
      console.error(err);
      showToast(`Failed to save to Belt ${beltNum}`, "error");
    }
  };

  const saveCustomizations = async () => {
    try {
      await axios.post(`${API_URL}/customizations`, { values: customValues });
      setSavedCustomValues(customValues);
      showToast("Values saved successfully!");
    } catch (err) {
      console.error(err);
      showToast("Failed to save values. Ensure backend is running.", "error");
    }
  };

  const handleAction = async (endpoint, modeName) => {
    try {
      setStatus(`Starting ${modeName}...`);
      const res = await axios.post(`${API_URL}/${endpoint}`);
      setStatus(res.data.message || `${modeName} executed.`);
    } catch (err) {
      console.error(err);
      setStatus(`Error: Could not connect to backend`);
    }
  };

  const handleNavClick = (item) => {
    if (item.type === 'page') {
      if (item.name === 'Team Viewer') {
        handleAction('open-teamviewer', 'Team Viewer');
        return;
      }
      if (item.name === 'Wi-Fi Connect') {
        handleAction('open-wifi', 'Wi-Fi Setup');
        return;
      }
      if (item.name === 'Settings' || item.name === 'Customizations') {
        setPendingPage(item.name);
        setShowLogin(true);
        setPassword('');
        setLoginError(false);
        return;
      }
      setActivePage(item.name);
    } else {
      setConfirmDialog({
        isOpen: true,
        type: item.name,
        title: `System ${item.name}`,
        message: `Are you sure you want to completely ${item.name.toLowerCase()} the device? All operations will be stopped.`
      });
    }
  };

  return (
    <div className="h-screen w-screen bg-gradient-to-br from-slate-50 via-slate-100 to-slate-200/80 text-slate-800 font-sans flex overflow-hidden selection:bg-blue-500/30 relative">

      {/* Subtle Grid Background */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#cbd5e1_1px,transparent_1px),linear-gradient(to_bottom,#cbd5e1_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)] opacity-20 pointer-events-none z-0"></div>

      {/* LEFT SIDEBAR (Navigation) */}
      <div className="w-[320px] bg-white/70 backdrop-blur-xl border-r border-slate-200/80 p-8 flex flex-col shadow-2xl z-20 shrink-0">
        {/* Company Branding */}
        <div className="flex items-center gap-4 mb-10 mt-2 pl-2">
          <div className="w-12 h-12 bg-white rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/20 overflow-hidden relative ring-1 ring-slate-100">
            <img src="/video.gif" alt="Logo" className="absolute w-full h-full object-cover scale-[1.35]" />
          </div>
          <div className="flex flex-col justify-center">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 leading-none">
              Keya <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Fusion</span>
            </h1>
            <p className="text-blue-600 text-[9px] font-bold tracking-[0.3em] uppercase mt-1">Technology</p>
          </div>
        </div>

        <nav className="flex flex-col gap-2 flex-1">
          <div className="text-xs font-bold tracking-widest text-slate-400 mb-2 pl-2">MAIN MENU</div>
          {navItems.filter(item => item.type === 'page').map(page => {
            const isActive = activePage === page.name;
            return (
              <button
                key={page.name}
                onClick={() => handleNavClick(page)}
                className={`group w-full flex items-center justify-start gap-4 px-4 py-3.5 rounded-2xl font-bold transition-all duration-300 ${isActive
                    ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/30 translate-x-1'
                    : 'bg-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                  }`}
              >
                <div className={`transition-colors ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-blue-500'}`}>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d={page.icon}></path>
                  </svg>
                </div>
                <span className="text-sm tracking-wide">{page.name}</span>
              </button>
            )
          })}
        </nav>

        {/* Action Buttons at bottom of sidebar */}
        <div className="flex flex-col gap-2 mt-auto">
          <div className="h-px w-full bg-slate-200/80 mb-4"></div>
          {navItems.filter(item => item.type === 'action').map(action => {
            const isRed = action.color === 'red';
            const isBlue = action.color === 'blue';

            let textClass = 'text-orange-600';
            let hoverClass = 'hover:bg-orange-50 hover:border-orange-200';
            let activeClass = 'active:bg-orange-100';

            if (isRed) {
              textClass = 'text-red-600';
              hoverClass = 'hover:bg-red-50 hover:border-red-200';
              activeClass = 'active:bg-red-100';
            } else if (isBlue) {
              textClass = 'text-blue-600';
              hoverClass = 'hover:bg-blue-50 hover:border-blue-200';
              activeClass = 'active:bg-blue-100';
            }

            return (
              <button
                key={action.name}
                onClick={() => handleNavClick(action)}
                className={`group w-full flex items-center justify-start gap-4 px-4 py-3.5 rounded-2xl font-bold transition-all duration-300 border border-transparent ${hoverClass} ${activeClass} ${textClass}`}
              >
                <svg className="w-5 h-5 opacity-80 group-hover:opacity-100" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d={action.icon}></path>
                </svg>
                <span className="text-sm tracking-wide">{action.name}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col p-8 pt-6 z-10 min-w-0">

        {/* TOP HEADER */}
        <div className="flex justify-between items-center mb-8 shrink-0">
          {/* Dynamic Page Title */}
          <div className="flex flex-col">
            <h2 className="text-4xl font-extrabold tracking-tight text-slate-800 drop-shadow-sm flex items-center gap-3">
              {activePage === 'Control Hub' && "System Control Hub"}
              {activePage === 'Air Valve' && (
                <>
                  <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl shadow-lg shadow-blue-500/20 text-white">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                  </div>
                  Air Valve Testing
                </>
              )}
              {activePage !== 'Control Hub' && activePage !== 'Air Valve' && activePage}
            </h2>
            <p className="text-slate-500 text-sm font-medium mt-2 max-w-lg">
              {activePage === 'Control Hub' && "Manage Python automation, grading scripts, and real-time operations."}
              {activePage === 'Air Valve' && "Manual testing interface for 15 belts and their respective 7 ports."}
            </p>
          </div>

          {/* Live Date/Time Display */}
          <div className="flex flex-col items-end text-right bg-white/60 backdrop-blur-md border border-slate-200/60 px-6 py-3 rounded-2xl shadow-sm">
            <span className="text-2xl font-black text-slate-800 tabular-nums tracking-tight leading-none">
              {currentDateTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
            <span className="text-xs font-bold text-blue-600 uppercase tracking-widest mt-1">
              {currentDateTime.toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric' })}
            </span>
          </div>
        </div>

        {/* Render Control Hub */}
        {activePage === 'Control Hub' ? (
          <div className="flex flex-col h-full w-full animate-in fade-in duration-500">

            {/* Main Layout Row */}
            <div className="flex flex-1 gap-6 min-h-0">

              {/* GRAPH AREA (Left/Middle) */}
              <div className="flex-1 bg-white/80 backdrop-blur-xl rounded-[2rem] border border-white p-6 shadow-xl shadow-slate-200/50 flex flex-col relative overflow-hidden group">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                    <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"></path></svg>
                    Live Grading Analytics
                  </h3>
                  <div className="px-3 py-1 bg-slate-50 text-xs font-semibold rounded-md border border-slate-200 text-slate-500">Waiting for Data</div>
                </div>

                {/* Live Animated Bar Chart */}
                <div className="flex-1 rounded-xl flex flex-col items-center justify-center transition-colors">
                  {graphData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={graphData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                        <XAxis dataKey="name" stroke="#94a3b8" tick={{ fill: '#64748b' }} tickLine={false} axisLine={false} />
                        <YAxis stroke="#94a3b8" tick={{ fill: '#64748b' }} tickLine={false} axisLine={false} allowDecimals={false} />
                        <Tooltip
                          cursor={{ fill: '#f8fafc', opacity: 0.8 }}
                          contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '8px', color: '#1e293b', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                          itemStyle={{ color: '#1e293b' }}
                        />
                        <Bar dataKey="count" radius={[4, 4, 0, 0]} animationDuration={1000}>
                          {graphData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="flex flex-col items-center justify-center text-slate-400">
                      <svg className="w-8 h-8 mb-3 animate-spin text-slate-300" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                      <span className="font-medium text-sm">Connecting to Data Stream...</span>
                    </div>
                  )}
                </div>
              </div>

              {/* CONTROLS SIDEBAR (Right side of content area) */}
              <div className="w-[340px] flex flex-col gap-6 h-full">

                {/* Control Panel */}
                <div className="bg-white/80 backdrop-blur-xl p-6 rounded-[2rem] border border-white shadow-xl shadow-slate-200/50 flex flex-col flex-1">
                  <h3 className="text-xl font-bold text-slate-800 mb-5 px-2 flex items-center gap-2">
                    <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
                    Action Commands
                  </h3>

                  <div className="flex flex-col gap-3">
                    <button
                      onClick={() => handleAction('run-default', 'Default Mode')}
                      className={`group relative w-full p-4 rounded-2xl transition-all active:scale-[0.98] flex items-center gap-4 border overflow-hidden ${currentMode === 'Default Mode' ? 'bg-gradient-to-r from-indigo-500 to-indigo-600 border-transparent shadow-lg shadow-indigo-500/30' : 'bg-white hover:bg-slate-50 border-slate-200 hover:border-indigo-300 shadow-sm text-slate-700'}`}
                    >
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${currentMode === 'Default Mode' ? 'bg-white/20 text-white' : 'bg-indigo-50 group-hover:bg-indigo-100 text-indigo-600'}`}>
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          {currentMode === 'Default Mode' ? (
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path>
                          ) : (
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd"></path>
                          )}
                        </svg>
                      </div>
                      <div className="text-left">
                        <span className={`block text-sm font-bold ${currentMode === 'Default Mode' ? 'text-white' : 'text-slate-800'}`}>Default Mode</span>
                        <span className={`block text-xs transition-colors ${currentMode === 'Default Mode' ? 'text-indigo-100' : 'text-slate-500 group-hover:text-indigo-600'}`}>Run standard sequence</span>
                      </div>
                    </button>

                    <button
                      onClick={() => handleAction('run-grading', 'Grading Mode')}
                      className={`group relative w-full p-4 rounded-2xl transition-all active:scale-[0.98] flex items-center gap-4 border overflow-hidden ${currentMode === 'Grading Mode' ? 'bg-gradient-to-r from-blue-500 to-blue-600 border-transparent shadow-lg shadow-blue-500/30' : 'bg-white hover:bg-slate-50 border-slate-200 hover:border-blue-300 shadow-sm text-slate-700'}`}
                    >
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${currentMode === 'Grading Mode' ? 'bg-white/20 text-white' : 'bg-blue-50 group-hover:bg-blue-100 text-blue-600'}`}>
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          {currentMode === 'Grading Mode' ? (
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path>
                          ) : (
                            <path d="M5 4a1 1 0 00-2 0v7.268a2 2 0 000 3.464V16a1 1 0 102 0v-1.268a2 2 0 000-3.464V4zM11 4a1 1 0 10-2 0v1.268a2 2 0 000 3.464V16a1 1 0 102 0V8.732a2 2 0 000-3.464V4zM16 3a1 1 0 011 1v7.268a2 2 0 010 3.464V16a1 1 0 11-2 0v-1.268a2 2 0 010-3.464V4a1 1 0 011-1z"></path>
                          )}
                        </svg>
                      </div>
                      <div className="text-left">
                        <span className={`block text-sm font-bold ${currentMode === 'Grading Mode' ? 'text-white' : 'text-slate-800'}`}>Grading Mode</span>
                        <span className={`block text-xs transition-colors ${currentMode === 'Grading Mode' ? 'text-blue-100' : 'text-slate-500 group-hover:text-blue-600'}`}>Run grading scripts</span>
                      </div>
                    </button>

                    <button
                      onClick={() => handleAction('run-color', 'Color Grading Mode')}
                      className={`group relative w-full p-4 rounded-2xl transition-all active:scale-[0.98] flex items-center gap-4 border overflow-hidden ${currentMode === 'Color Grading Mode' ? 'bg-gradient-to-r from-purple-500 to-purple-600 border-transparent shadow-lg shadow-purple-500/30' : 'bg-white hover:bg-slate-50 border-slate-200 hover:border-purple-300 shadow-sm hover:shadow-md text-slate-700'}`}
                    >
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${currentMode === 'Color Grading Mode' ? 'bg-white/20 text-white' : 'bg-purple-50 group-hover:bg-purple-100 text-purple-600'}`}>
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          {currentMode === 'Color Grading Mode' ? (
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path>
                          ) : (
                            <path fillRule="evenodd" d="M4 2a2 2 0 00-2 2v11a3 3 0 106 0V4a2 2 0 00-2-2H4zm1 14a1 1 0 100-2 1 1 0 000 2zm5-1.757l4.9-4.9a2 2 0 000-2.828L13.485 5.1a2 2 0 00-2.828 0L10 5.757v8.486zM16 18H9.071l6-6H16a2 2 0 012 2v2a2 2 0 01-2 2z" clipRule="evenodd"></path>
                          )}
                        </svg>
                      </div>
                      <div className="text-left">
                        <span className={`block text-base font-bold ${currentMode === 'Color Grading Mode' ? 'text-white' : 'text-slate-800'}`}>Color Grading</span>
                        <span className={`block text-xs transition-colors ${currentMode === 'Color Grading Mode' ? 'text-purple-100' : 'text-slate-500 group-hover:text-purple-600'}`}>Run color scripts</span>
                      </div>
                    </button>
                  </div>

                  <div className="mt-auto pt-4">
                    <button
                      onClick={() => handleAction('stop-all', 'Stop All')}
                      className="w-full p-4 bg-rose-50 hover:bg-rose-500 text-rose-600 hover:text-white font-bold text-sm uppercase tracking-wider rounded-xl transition-all active:scale-[0.98] border border-rose-200 hover:border-rose-500 shadow-sm hover:shadow flex justify-center items-center gap-2"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path></svg>
                      Emergency Stop All
                    </button>
                  </div>

                </div>

                {/* Status Console Mini */}
                <div className="bg-white/80 backdrop-blur-xl p-5 rounded-3xl border border-white shadow-xl shadow-slate-200/50">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.6)]"></div>
                    <span className="font-semibold text-slate-500 text-xs uppercase tracking-wider">System Terminal</span>
                  </div>
                  <div className="font-mono text-xs text-slate-600 bg-slate-50 p-4 rounded-xl border border-slate-200/60 overflow-hidden text-ellipsis whitespace-nowrap shadow-inner">
                    &gt; {status}
                  </div>
                </div>

              </div>
            </div>
          </div>
        ) : activePage === 'Air Valve' ? (
          <div className="flex flex-col h-full w-full animate-in fade-in duration-500 overflow-hidden">

            <div className="flex-1 bg-white/80 backdrop-blur-xl border border-white rounded-[2rem] p-6 shadow-xl shadow-slate-200/50 flex flex-col overflow-hidden">

              {/* Pagination Tabs */}
              <div className="flex gap-3 mb-6 justify-center shrink-0">
                {[1, 2, 3].map(pageNum => (
                  <button
                    key={pageNum}
                    onClick={() => setAirValvePage(pageNum)}
                    className={`px-8 py-3 rounded-xl font-bold text-lg transition-all border ${airValvePage === pageNum
                        ? 'bg-blue-600 text-white border-blue-700 shadow-md shadow-blue-500/20'
                        : 'bg-white text-slate-500 border-slate-200 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50'
                      }`}
                  >
                    Page {pageNum} <span className="text-sm font-medium opacity-80 ml-1">(Belts {(pageNum - 1) * 5 + 1}-{pageNum * 5})</span>
                  </button>
                ))}
              </div>

              <div className="flex-1 flex flex-col min-h-0">
                <div className="flex-1 flex flex-col gap-3 h-full">
                  {Array.from({ length: 5 }, (_, i) => (airValvePage - 1) * 5 + i + 1).map(beltId => (
                    <div key={beltId} className="flex-1 flex items-center gap-4 p-3 bg-slate-50 border border-slate-200 rounded-xl hover:border-blue-300 hover:shadow-sm transition-all group min-h-0">
                      <div className="w-32 xl:w-40 h-full font-black text-slate-800 text-2xl xl:text-3xl bg-white rounded-lg border border-slate-200 flex items-center justify-center shadow-sm group-hover:border-blue-400 group-hover:text-blue-700 transition-colors shrink-0">
                        Belt {beltId}
                      </div>
                      <div className="flex gap-3 flex-1 h-full">
                        {[11, 12, 13, 14, 15, 16, 21].map(portId => (
                          <button
                            key={portId}
                            onClick={async (e) => {
                              const btn = e.currentTarget;
                              btn.classList.add('bg-blue-500', 'text-white', 'border-blue-600', 'shadow-inner');
                              btn.classList.remove('bg-white', 'text-slate-600', 'border-slate-200', 'hover:border-blue-400', 'hover:text-blue-600');
                              setTimeout(() => {
                                btn.classList.remove('bg-blue-500', 'text-white', 'border-blue-600', 'shadow-inner');
                                btn.classList.add('bg-white', 'text-slate-600', 'border-slate-200', 'hover:border-blue-400', 'hover:text-blue-600');
                              }, 300);

                              try {
                                await axios.post(`${API_URL}/fire-valve`, { belt_id: beltId, port_id: portId });
                              } catch (err) {
                                console.error(err);
                              }
                            }}
                            className="flex-1 rounded-lg border border-slate-200 bg-white hover:border-blue-400 hover:text-blue-600 text-slate-600 font-bold text-xl xl:text-2xl transition-all active:scale-[0.97] shadow-sm flex flex-col justify-center items-center"
                          >
                            <span className="text-[10px] xl:text-xs font-semibold uppercase tracking-wider opacity-60 mb-0.5">Port</span>
                            {portId}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : activePage === 'Customizations' ? (
          <div className="flex flex-col h-full w-full animate-in fade-in duration-500 overflow-hidden">
            <div className="flex-1 flex gap-8 overflow-hidden">

              {/* Left Side: Input Form */}
              <div className="flex-1 flex flex-col bg-white/80 backdrop-blur-xl border border-white p-6 rounded-[2rem] shadow-xl shadow-slate-200/50">

                <div className="flex gap-4 px-4 mb-2 text-slate-500 font-bold text-sm tracking-wider uppercase shrink-0">
                  <div className="w-24 text-center">Grade</div>
                  <div className="flex-1 text-center">Min Value</div>
                  <div className="flex-1 text-center">Max Value</div>
                </div>

                <div className="flex flex-col gap-5 flex-1 px-4 mb-4">
                  {['400', '320', '240', '210', '180'].map(level => (
                    <div key={level} className="flex gap-6 items-center flex-1 min-h-0">
                      <div className="w-24 h-full text-center font-black text-2xl text-slate-800 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-center shrink-0">{level}</div>
                      <div className="flex-1 h-full">
                        <input
                          type="text"
                          readOnly
                          value={customValues[level].min}
                          onClick={() => setActiveInput({ level, field: 'min' })}
                          placeholder="Min"
                          className="w-full h-full bg-white border-2 border-slate-200 rounded-xl px-4 text-center font-bold text-2xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm transition-all cursor-pointer text-slate-700"
                        />
                      </div>
                      <div className="flex-1 h-full">
                        <input
                          type="text"
                          readOnly
                          value={customValues[level].max}
                          onClick={() => setActiveInput({ level, field: 'max' })}
                          placeholder="Max"
                          className="w-full h-full bg-white border-2 border-slate-200 rounded-xl px-4 text-center font-bold text-2xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm transition-all cursor-pointer text-slate-700"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right Side: Display Values & OK Button */}
              <div className="w-[280px] flex flex-col gap-6 shrink-0 h-full">

                {/* Display Screen */}
                <div className="flex-1 flex flex-col bg-slate-800 text-slate-50 p-5 rounded-2xl shadow-lg relative overflow-hidden min-h-0">
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-400 to-indigo-500"></div>
                  <h3 className="text-sm font-bold text-blue-400 mb-5 uppercase tracking-wider flex items-center justify-center gap-1.5 text-center shrink-0">
                    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    Saved Data
                  </h3>

                  <div className="flex flex-col gap-2 flex-1 overflow-y-auto pr-1">
                    {['400', '320', '240', '210', '180'].map(level => (
                      <div key={`saved-${level}`} className="flex justify-between items-center border-b border-slate-700 pb-2 last:border-0">
                        <span className="font-black text-xl text-white">{level}</span>
                        <div className="flex gap-3">
                          <div className="flex flex-col items-end">
                            <span className="text-[9px] text-slate-400 uppercase tracking-wider mb-0.5">Min</span>
                            <span className="font-mono font-bold text-blue-400 text-sm">{savedCustomValues[level].min || '--'}</span>
                          </div>
                          <div className="flex flex-col items-end">
                            <span className="text-[9px] text-slate-400 uppercase tracking-wider mb-0.5">Max</span>
                            <span className="font-mono font-bold text-indigo-400 text-sm">{savedCustomValues[level].max || '--'}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* OK Button */}
                <button
                  onClick={saveCustomizations}
                  className="w-full h-32 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl font-black text-4xl shadow-lg shadow-blue-500/30 transition-all active:scale-[0.98] flex justify-center items-center gap-3 border border-blue-500 shrink-0"
                >
                  <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7"></path></svg>
                  OK
                </button>

              </div>

            </div>
          </div>
        ) : activePage === 'Settings' ? (
          <div className="flex h-full w-full gap-6 animate-in fade-in duration-500">
            {/* Left side content placeholder */}
            {activeSettingsModule === 'Camera' ? (
              <div className="flex-1 flex flex-col h-full bg-white/80 backdrop-blur-xl border border-white rounded-[2rem] overflow-hidden shadow-xl shadow-slate-200/50">
                <div className="flex items-center justify-between p-5 border-b border-slate-200 bg-slate-50/50">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center shadow-sm">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path></svg>
                    </div>
                    <h2 className="text-xl font-bold text-slate-800">Camera Settings</h2>
                  </div>
                  <button onClick={() => setActiveSettingsModule(null)} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 rounded-lg transition-colors">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                  </button>
                </div>

                <div className="flex h-full w-full p-6 gap-6 overflow-y-auto bg-slate-50/30">
                  {/* Reference Section (Left) */}
                  <div className="flex-1 flex flex-col bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-800 mb-6">Reference</h3>

                    <div className="flex flex-col gap-4 flex-1">
                      {[0, 1, 2].map(idx => (
                        <div key={idx} className="flex flex-col gap-1">
                          <div className="flex items-center bg-slate-50 border border-slate-200 rounded-xl overflow-hidden focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
                            <div className="bg-slate-100/80 px-4 py-3 text-slate-500 font-bold border-r border-slate-200">
                              CAM
                            </div>
                            <input
                              type="text"
                              value={cameraRefs[idx]}
                              onChange={(e) => {
                                const newRefs = [...cameraRefs];
                                newRefs[idx] = e.target.value;
                                setCameraRefs(newRefs);
                              }}
                              className="w-full p-3 text-base font-bold outline-none text-slate-800 bg-transparent"
                              placeholder={`e.g. ${idx * 2 + 1}`}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="mt-6">
                      <button
                        onClick={saveCameraRefs}
                        className="w-full py-3 bg-slate-800 hover:bg-slate-900 text-white text-base font-bold rounded-xl shadow-sm transition-all active:scale-95 flex items-center justify-center"
                      >
                        Save Configuration
                      </button>
                    </div>
                  </div>

                  {/* Check-in Section (Right) */}
                  <div className="flex-1 flex flex-col bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-800 mb-6">Check INs</h3>

                    <div className="flex flex-col gap-4 flex-1">
                      {isCheckingCameras ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-4">
                          <svg className="w-8 h-8 animate-spin text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                          <p className="font-semibold text-sm">Scanning cameras...</p>
                        </div>
                      ) : connectedCameras.length > 0 ? (
                        connectedCameras.map((camName, idx) => (
                          <div key={idx} className="flex flex-col gap-1 relative">
                            <div className="flex items-center bg-slate-50 border border-slate-200 rounded-xl overflow-hidden transition-all">
                              <input
                                type="text"
                                readOnly
                                value={camName}
                                className="w-full p-3 text-base font-bold outline-none text-slate-800 bg-transparent cursor-default"
                              />
                            </div>
                            <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
                              <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-slate-400 border border-dashed border-slate-200 rounded-xl">
                          <svg className="w-10 h-10 mb-2 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path></svg>
                          <p className="font-semibold text-sm text-slate-500">No Cameras Found</p>
                        </div>
                      )}
                    </div>

                    <div className="mt-6">
                      <button
                        onClick={checkCameras}
                        disabled={isCheckingCameras}
                        className="w-full py-3 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-base font-bold rounded-xl shadow-sm transition-all active:scale-95 flex items-center justify-center gap-2"
                      >
                        {isCheckingCameras ? (
                          <><svg className="w-4 h-4 animate-spin text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> Refreshing...</>
                        ) : (
                          'Refresh Status'
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ) : activeSettingsModule === 'Comports' ? (
              <div className="flex-1 flex flex-col h-full bg-white/80 backdrop-blur-xl border border-white rounded-[2rem] overflow-hidden shadow-xl shadow-slate-200/50">
                <div className="flex items-center justify-between p-5 border-b border-slate-200 bg-slate-50/50">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-orange-50 text-orange-600 rounded-lg flex items-center justify-center shadow-sm border border-orange-100">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                    </div>
                    <h2 className="text-xl font-bold text-slate-800">Comports Settings</h2>
                  </div>
                  <button onClick={() => setActiveSettingsModule(null)} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 rounded-lg transition-colors">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                  </button>
                </div>

                <div className="flex h-full w-full p-6 gap-6 overflow-y-auto bg-slate-50/30">
                  {/* Reference Section (Left) */}
                  <div className="flex-1 flex flex-col bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-800 mb-6">Reference</h3>

                    <div className="flex flex-col gap-4 flex-1">
                      {[0, 1, 2].map(idx => (
                        <div key={idx} className="flex flex-col gap-1">
                          <div className="flex items-center bg-slate-50 border border-slate-200 rounded-xl overflow-hidden focus-within:border-orange-400 focus-within:ring-2 focus-within:ring-orange-100 transition-all">
                            <div className="bg-slate-100/80 px-4 py-3 text-slate-500 font-bold border-r border-slate-200">
                              COM
                            </div>
                            <input
                              type="text"
                              value={comportRefs[idx]}
                              onChange={(e) => {
                                const newRefs = [...comportRefs];
                                newRefs[idx] = e.target.value;
                                setComportRefs(newRefs);
                              }}
                              className="w-full p-3 text-base font-bold outline-none text-slate-800 bg-transparent"
                              placeholder={`e.g. ${idx + 1}`}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="mt-6">
                      <button
                        onClick={saveComportRefs}
                        className="w-full py-3 bg-slate-800 hover:bg-slate-900 text-white text-base font-bold rounded-xl shadow-sm transition-all active:scale-95 flex items-center justify-center"
                      >
                        OK
                      </button>
                    </div>
                  </div>

                  {/* Check-in Section (Right) */}
                  <div className="flex-1 flex flex-col bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-800 mb-6">Check INs</h3>

                    <div className="flex flex-col gap-4 flex-1">
                      {isCheckingComports ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-4">
                          <svg className="w-8 h-8 animate-spin text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                          <p className="font-semibold text-sm">Scanning comports...</p>
                        </div>
                      ) : connectedComports.length > 0 ? (
                        connectedComports.map((comName, idx) => (
                          <div key={idx} className="flex flex-col gap-1 relative">
                            <div className="flex items-center bg-slate-50 border border-slate-200 rounded-xl overflow-hidden transition-all">
                              <input
                                type="text"
                                readOnly
                                value={comName}
                                className="w-full p-3 text-base font-bold outline-none text-slate-800 bg-transparent cursor-default"
                              />
                            </div>
                            <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
                              <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-slate-400 border border-dashed border-slate-200 rounded-xl">
                          <svg className="w-10 h-10 mb-2 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path></svg>
                          <p className="font-semibold text-sm text-slate-500">No Comports Found</p>
                        </div>
                      )}
                    </div>

                    <div className="mt-6">
                      <button
                        onClick={checkComports}
                        disabled={isCheckingComports}
                        className="w-full py-3 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-base font-bold rounded-xl shadow-sm transition-all active:scale-95 flex items-center justify-center gap-2"
                      >
                        {isCheckingComports ? (
                          <><svg className="w-4 h-4 animate-spin text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> Refreshing...</>
                        ) : (
                          'Refresh'
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 bg-white/80 backdrop-blur-xl border border-white rounded-[2rem] p-8 shadow-xl shadow-slate-200/50 flex flex-col items-center relative overflow-y-auto custom-scrollbar">
                <h2 className="text-3xl font-extrabold text-slate-800 mb-8 self-start flex items-center gap-3">
                  <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                  System Configuration
                </h2>
                
                <div className="w-full max-w-2xl bg-slate-50 border border-slate-200 p-8 rounded-3xl shadow-sm flex flex-col items-center gap-6">
                   <div className="flex w-full items-center gap-4">
                     <div 
                        onClick={() => {
                          if (!showMainSettingsNumpad) {
                            setMainSettingsValue("");
                            setShowMainSettingsNumpad(true);
                            setShowBeltsGrid(false);
                            setMainSettingsSelectedBelt(null);
                          }
                        }}
                        className={`flex-1 h-16 bg-white border-2 rounded-2xl flex items-center px-6 text-3xl tracking-widest font-black cursor-pointer transition-all ${showMainSettingsNumpad ? 'border-blue-500 shadow-[0_0_0_4px_rgba(59,130,246,0.15)] text-blue-600 scale-[1.02]' : 'border-slate-200 text-slate-800 hover:border-blue-300'}`}
                     >
                       {mainSettingsValue || <span className="text-slate-300 font-medium tracking-normal text-xl">Enter Value...</span>}
                     </div>
                     <button 
                       onClick={() => {
                         setShowMainSettingsNumpad(false);
                         setShowBeltsGrid(true);
                       }}
                       className="h-16 px-12 bg-indigo-600 hover:bg-indigo-700 text-white text-xl font-bold rounded-2xl shadow-lg shadow-indigo-500/30 transition-all active:scale-95 flex items-center gap-2"
                     >
                       <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                       OK
                     </button>
                   </div>

                   {/* Inline Numpad */}
                   {showMainSettingsNumpad && (
                     <div className="w-[320px] bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xl mt-2 animate-in zoom-in-95 fade-in duration-200">
                        <div className="flex justify-between items-center mb-4">
                          <h3 className="text-sm font-bold text-slate-400 tracking-widest">NUMPAD</h3>
                          <button onClick={() => { setShowMainSettingsNumpad(false); setShowBeltsGrid(true); }} className="text-slate-400 hover:text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-full p-1 transition-colors">
                             <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                          </button>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                          {[1, 2, 3, 4, 5, 6, 7, 8, 9, '.', 0, 'DEL'].map((num) => (
                            <button
                              key={num}
                              disabled={num === '.'}
                              onClick={() => {
                                if (num === 'DEL') {
                                  setMainSettingsValue(prev => prev.slice(0, -1));
                                } else {
                                  setMainSettingsValue(prev => prev.length >= 8 ? num.toString() : prev + num);
                                }
                              }}
                              className={`h-14 rounded-xl font-black text-xl transition-all active:scale-95 flex justify-center items-center shadow-sm ${num === 'DEL' ? 'bg-red-50 text-red-600 hover:bg-red-100' : num === '.' ? 'bg-slate-100 text-slate-300 cursor-not-allowed' : 'bg-slate-50 text-slate-800 border border-slate-200 hover:border-blue-300 hover:text-blue-600'}`}
                            >
                              {num === 'DEL' ? <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z"></path></svg> : num}
                            </button>
                          ))}
                        </div>
                     </div>
                   )}
                </div>

                {showBeltsGrid && (
                  <div className="w-full mt-12 px-2 animate-in slide-in-from-bottom-4 fade-in duration-300">
                     <h3 className="text-lg font-bold text-slate-600 mb-4 flex items-center gap-2">
                       <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
                       Select Target Belt
                     </h3>
                     <div className="grid grid-cols-5 gap-4">
                       {[...Array(15)].map((_, i) => (
                         <button
                           key={i+1}
                           onClick={() => saveMainSettingsToBelt(i+1)}
                           className={`h-16 rounded-2xl font-bold text-lg border-2 transition-all flex items-center justify-center ${mainSettingsSelectedBelt === i+1 ? 'bg-blue-50 border-blue-500 text-blue-700 shadow-[0_0_0_4px_rgba(59,130,246,0.15)] scale-105 z-10' : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300 hover:shadow-md'}`}
                         >
                           Belt {i+1}
                         </button>
                       ))}
                     </div>
                  </div>
                )}
              </div>
            )}

            {/* Right side buttons */}
            <div className="w-[340px] flex flex-col gap-6 h-full">
              <div className="bg-white/80 backdrop-blur-xl p-6 rounded-[2rem] border border-white shadow-xl shadow-slate-200/50 flex flex-col flex-1">
                <h3 className="text-lg font-bold text-slate-800 mb-6 px-2 flex items-center gap-2">
                  <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
                  Configurations
                </h3>

                <div className="flex flex-col gap-4">
                  {/* Time Setting Button */}
                  <button onClick={() => setActivePage('Time Setting')} className="group relative w-full p-4 bg-white hover:bg-slate-50 text-slate-700 rounded-xl shadow-sm hover:shadow transition-all active:scale-[0.98] flex items-center gap-4 border border-slate-200 hover:border-indigo-300">
                    <div className="w-10 h-10 rounded-lg bg-indigo-50 group-hover:bg-indigo-100 flex items-center justify-center transition-colors shrink-0">
                      <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </div>
                    <span className="text-base font-bold text-slate-800 text-left">Time Setting</span>
                  </button>

                  {/* Camera Button */}
                  <button onClick={() => setActiveSettingsModule('Camera')} className={`group relative w-full p-4 bg-white hover:bg-slate-50 text-slate-700 rounded-xl shadow-sm hover:shadow transition-all active:scale-[0.98] flex items-center gap-4 border ${activeSettingsModule === 'Camera' ? 'border-blue-400 bg-blue-50/50' : 'border-slate-200 hover:border-blue-300'}`}>
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors shrink-0 ${activeSettingsModule === 'Camera' ? 'bg-blue-100' : 'bg-blue-50 group-hover:bg-blue-100'}`}>
                      <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                    </div>
                    <span className="text-base font-bold text-slate-800 text-left">Camera</span>
                  </button>

                  {/* Comports Button */}
                  <button onClick={() => setActiveSettingsModule('Comports')} className={`group relative w-full p-4 bg-white hover:bg-slate-50 text-slate-700 rounded-xl shadow-sm hover:shadow transition-all active:scale-[0.98] flex items-center gap-4 border ${activeSettingsModule === 'Comports' ? 'border-orange-400 bg-orange-50/50' : 'border-slate-200 hover:border-orange-300'}`}>
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors shrink-0 ${activeSettingsModule === 'Comports' ? 'bg-orange-100' : 'bg-orange-50 group-hover:bg-orange-100'}`}>
                      <svg className="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                    </div>
                    <span className="text-base font-bold text-slate-800 text-left">Comports</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : activePage === 'Time Setting' ? (
          <div className="flex h-full w-full gap-6 animate-in fade-in duration-500">

            {/* Main Area (Matrix of 15 belts x 7 boxes) */}
            <div className="flex-1 flex flex-col bg-white/80 backdrop-blur-xl border border-white rounded-[2rem] p-6 shadow-xl shadow-slate-200/50 min-w-0">

              {/* Scrollable Matrix Table */}
              <div className="flex-1 overflow-y-auto custom-scrollbar border border-slate-200 rounded-xl bg-slate-50/50">
                <table className="w-full text-center border-collapse">
                  <thead className="sticky top-0 bg-slate-100/90 backdrop-blur-sm shadow-sm z-10">
                    <tr>
                      <th className="p-4 text-slate-500 font-bold border-b border-slate-200">BELT</th>
                      {[...Array(7)].map((_, i) => (
                        <th key={i} className="p-4 text-slate-500 font-bold border-b border-slate-200">BOX {i + 1}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...Array(15)].map((_, r) => {
                      const beltId = (r + 1).toString();
                      return (
                        <tr key={beltId} className="hover:bg-white transition-colors border-b border-slate-200">
                          <td className="p-3 font-black text-slate-800 bg-white">{beltId}</td>
                          {[...Array(7)].map((_, c) => {
                            const isSelected = activeTimeInput && activeTimeInput.belt === beltId && activeTimeInput.idx === c;
                            const val = timeSettingsValues[beltId]?.[c];
                            return (
                              <td key={c} className="p-2">
                                <div
                                  onClick={() => setActiveTimeInput({ belt: beltId, idx: c })}
                                  className={`h-12 flex items-center justify-center text-xl font-bold rounded-lg cursor-pointer transition-all border
                                    ${isSelected ? 'bg-indigo-50 border-indigo-400 text-indigo-700 shadow-inner scale-[1.03]' : 'bg-white border-slate-200 text-slate-700 hover:border-indigo-300'}
                                  `}
                                >
                                  {val ? val : <span className="text-slate-300">0000</span>}
                                </div>
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Number Pad for Time Setting */}
            <div className="w-[300px] shrink-0 flex flex-col gap-3">
              <button
                onClick={() => setActivePage('Settings')}
                className="w-full py-3.5 bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900 border-2 border-slate-200 rounded-2xl font-bold transition-all active:scale-95 flex items-center justify-center gap-2 mb-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
                Back to Settings
              </button>

              <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-sm">
                <h3 className="text-sm font-bold text-slate-400 tracking-widest text-center mb-4">NUMPAD</h3>
                <div className="grid grid-cols-3 gap-3">
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, '.', 0, 'DEL'].map((num) => (
                    <button
                      key={num}
                      onClick={() => handleTimeNumberClick(num)}
                      disabled={num === '.'}
                      className={`h-16 rounded-xl font-black text-2xl transition-all active:scale-95 flex justify-center items-center shadow-sm
                          ${num === 'DEL' ? 'bg-red-50 text-red-600 hover:bg-red-100' :
                          num === '.' ? 'bg-slate-100 text-slate-300 cursor-not-allowed' :
                            'bg-slate-50 text-slate-800 border border-slate-200 hover:border-indigo-300 hover:text-indigo-600'}
                        `}
                    >
                      {num === 'DEL' ? (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z"></path></svg>
                      ) : num}
                    </button>
                  ))}
                </div>
              </div>

              {/* Buttons placed below the Numpad */}
              <div className="flex flex-col gap-3">
                <button
                  onClick={applyToAllBelts}
                  className="w-full py-4 bg-amber-500 hover:bg-amber-600 text-white rounded-2xl font-bold shadow-lg shadow-amber-500/30 transition-all active:scale-95 flex items-center justify-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                  Apply Belt 1 to All
                </button>
                <button
                  onClick={saveTimeSettings}
                  className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-bold shadow-lg shadow-indigo-500/30 transition-all active:scale-95 flex items-center justify-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                  Save All Settings
                </button>
              </div>
            </div>
          </div>
        ) : activePage === 'Camera Setting' ? (
          <div className="flex-1 flex flex-col h-full bg-white border border-slate-200 rounded-[2rem] overflow-hidden shadow-sm">
            <div className="flex items-center justify-between p-5 border-b border-slate-200 bg-slate-50/50">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-lg flex items-center justify-center shadow-sm border border-blue-100">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path></svg>
                </div>
                <h2 className="text-xl font-bold text-slate-800">Camera Settings</h2>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setIsPreviewing(true)}
                  className="px-4 py-2 bg-emerald-100 text-emerald-700 hover:bg-emerald-200 font-bold rounded-lg transition-colors flex items-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                  Live Preview
                </button>
                <button
                  onClick={() => setIsPreviewing(false)}
                  className="px-4 py-2 bg-rose-100 text-rose-700 hover:bg-rose-200 font-bold rounded-lg transition-colors flex items-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                  Stop Preview
                </button>
              </div>
            </div>

            <div className="flex flex-row h-full w-full p-4 gap-4 bg-slate-50/50 overflow-hidden">
              
              {/* Camera Selection Sidebar */}
              <div className="w-24 flex flex-col gap-2">
                {["1", "2", "3"].map(camIdx => (
                  <button
                    key={camIdx}
                    onClick={() => {
                      setActiveCamParamIdx(camIdx);
                      // Force a tiny delay so the src reloads cleanly
                      if (isPreviewing) {
                        setIsPreviewing(false);
                        setTimeout(() => setIsPreviewing(true), 50);
                      }
                    }}
                    className={`flex-1 rounded-xl font-bold text-sm transition-all border-2 flex items-center justify-center ${activeCamParamIdx === camIdx ? 'bg-blue-600 text-white border-blue-600 shadow-md shadow-blue-500/30' : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300 hover:text-blue-600'}`}
                  >
                    Camera {camIdx}
                  </button>
                ))}
              </div>

              {/* Video Feed Embedded View */}
              <div id="camera-feed-container" className="flex-1 bg-black rounded-2xl overflow-hidden relative shadow-inner border-2 border-slate-800 flex items-center justify-center group">
                {/* Full Screen Toggle Button */}
                <button
                  onClick={toggleFullScreen}
                  className="absolute top-4 right-4 p-2 bg-black/50 hover:bg-black/80 text-white rounded-lg opacity-0 group-hover:opacity-100 transition-opacity z-10 backdrop-blur-sm border border-white/20"
                  title="Toggle Fullscreen"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path></svg>
                </button>
                {isPreviewing ? (
                  <img 
                    key={activeCamParamIdx}
                    src={`${API_URL}/video_feed/${activeCamParamIdx}`} 
                    className="w-full h-full object-contain"
                    alt={`Camera ${activeCamParamIdx} Live Feed`}
                    onError={(e) => {
                      e.target.style.display = 'none';
                      const parent = e.target.parentElement;
                      let errorDiv = parent.querySelector('.error-msg');
                      if (!errorDiv) {
                        errorDiv = document.createElement('div');
                        errorDiv.className = 'error-msg absolute text-red-500 font-bold flex flex-col items-center';
                        errorDiv.innerHTML = '<svg class="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg><span>Connection Failed</span>';
                        parent.appendChild(errorDiv);
                      }
                    }}
                  />
                ) : (
                  <div className="text-slate-600 flex flex-col items-center font-bold">
                    <svg className="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                    Preview Offline
                  </div>
                )}
              </div>

              {/* Settings and Zones Tabs Side Panel */}
              <div className="w-[22rem] bg-white border border-slate-200 rounded-[1.5rem] p-4 shadow-sm flex flex-col overflow-hidden">
                <div className="flex border-b border-slate-200 mb-3 pb-1">
                  <button
                    onClick={() => setZonesTab('camera')}
                    className={`flex-1 pb-2 font-bold text-sm text-center border-b-2 transition-all ${zonesTab === 'camera' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                  >
                    Camera Params
                  </button>
                  <button
                    onClick={() => setZonesTab('zones')}
                    className={`flex-1 pb-2 font-bold text-sm text-center border-b-2 transition-all ${zonesTab === 'zones' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                  >
                    Zones Config
                  </button>
                </div>
                
                {zonesTab === 'camera' ? (
                  <>
                    <div className="flex flex-col gap-3 flex-1 overflow-y-auto pr-2 custom-scrollbar">
                      {[
                        { key: 'exposure', label: 'Exposure', min: 100, max: 100000 },
                        { key: 'gain', label: 'Gain (Brightness)', min: 0, max: 20 },
                        { key: 'width', label: 'Width (Crop)', min: 32, max: 2448 },
                        { key: 'height', label: 'Height (Crop)', min: 8, max: 2048 },
                        { key: 'offsetX', label: 'Offset X', min: 0, max: 2448 },
                        { key: 'offsetY', label: 'Offset Y', min: 0, max: 2048 },
                      ].map(param => (
                        <div key={param.key} className="flex flex-col gap-1.5 p-2.5 bg-slate-50 rounded-xl border border-slate-100">
                          <div className="flex justify-between items-center">
                            <label className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">{param.label}</label>
                            <input
                              type="number"
                              min={param.min}
                              max={param.max}
                              value={cameraParams[activeCamParamIdx]?.[param.key] ?? 0}
                              onChange={(e) => updateCameraParam(param.key, e.target.value)}
                              className="w-20 p-1 bg-white border border-slate-200 rounded-lg font-bold text-xs text-slate-800 outline-none focus:border-blue-500 text-center"
                            />
                          </div>
                          <input 
                            type="range" 
                            min={param.min} 
                            max={param.max} 
                            value={cameraParams[activeCamParamIdx]?.[param.key] ?? 0}
                            onChange={(e) => updateCameraParam(param.key, e.target.value)}
                            className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                          />
                        </div>
                      ))}
                    </div>

                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <button
                        onClick={saveCameraParamsData}
                        className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl shadow-md shadow-blue-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7"></path></svg>
                        Save All
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    {/* Zone Selector Buttons */}
                    <div className="flex gap-1.5 mb-3 overflow-x-auto pb-1.5 custom-scrollbar">
                      {zones.map((z, idx) => (
                        <button
                          key={idx}
                          onClick={() => setActiveZoneIdx(idx)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${activeZoneIdx === idx ? 'bg-blue-600 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                        >
                          {z.name}
                        </button>
                      ))}
                    </div>

                    {zones[activeZoneIdx] ? (
                      <div className="flex flex-col gap-3 flex-1 overflow-y-auto pr-2 custom-scrollbar">
                        {[
                          { label: 'X (Left/Right)', max: 2448, idx: 0 },
                          { label: 'Y (Top/Bottom)', max: 2048, idx: 1 },
                          { label: 'Width', max: 2448, idx: 2 },
                          { label: 'Height', max: 2048, idx: 3 }
                        ].map(param => (
                          <div key={param.idx} className="flex flex-col gap-1.5 p-2.5 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="flex justify-between items-center">
                              <label className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">{param.label}</label>
                              <input
                                type="number"
                                min={0}
                                max={param.max}
                                value={zones[activeZoneIdx].zone[param.idx] ?? 0}
                                onChange={(e) => updateZoneParam(activeZoneIdx, param.idx, e.target.value)}
                                className="w-20 p-1 bg-white border border-slate-200 rounded-lg font-bold text-xs text-slate-800 outline-none focus:border-blue-500 text-center"
                              />
                            </div>
                            <input 
                              type="range" 
                              min={0} 
                              max={param.max} 
                              value={zones[activeZoneIdx].zone[param.idx] ?? 0}
                              onChange={(e) => updateZoneParam(activeZoneIdx, param.idx, e.target.value)}
                              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                            />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-slate-500 text-center py-8 font-bold">No Zones Loaded</div>
                    )}

                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <button
                        onClick={saveZonesConfig}
                        className="w-full py-2.5 bg-red-600 hover:bg-red-700 text-white text-sm font-bold rounded-xl shadow-md shadow-red-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7"></path></svg>
                        Save All Zones
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* Render Other Pages */
          <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-slate-200 rounded-2xl bg-slate-50/50 backdrop-blur-sm animate-in fade-in duration-500">
            <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mb-6 border border-slate-200 shadow-sm">
              <svg className="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
            </div>
            <h2 className="text-3xl font-bold text-slate-800 mb-2">{activePage}</h2>
            <p className="text-slate-500 font-medium">This module is currently under construction.</p>
          </div>
        )}

      </div>

      {/* The RIGHT SIDE MAIN NAVBAR has been removed and replaced by the Left Sidebar above */}

      {/* Login Password Modal */}
      {showLogin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 p-8 rounded-2xl shadow-xl max-w-sm w-full animate-in zoom-in-95 duration-200">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center shadow-sm border border-blue-100">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
              </div>
            </div>
            <h3 className="text-2xl font-black text-center text-slate-800 mb-2">Restricted Access</h3>
            <p className="text-center text-slate-500 text-sm mb-6">Enter administrator password to access {pendingPage}.</p>

            <form onSubmit={(e) => {
              e.preventDefault();
              if (password === '1234') {
                setActivePage(pendingPage);
                setShowLogin(false);
              } else {
                setLoginError(true);
              }
            }}>
              <input
                type="password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setLoginError(false); }}
                className={`w-full px-4 py-3 rounded-xl border ${loginError ? 'border-red-500 bg-red-50 text-red-700' : 'border-slate-200 bg-slate-50 text-slate-800'} focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all mb-4 text-center font-black tracking-[0.3em] text-2xl shadow-sm`}
                placeholder="••••"
                readOnly
              />
              {loginError && <p className="text-red-500 text-xs text-center font-bold mb-4 -mt-2">Incorrect password. Please try again.</p>}

              {/* On-Screen Numpad */}
              <div className="grid grid-cols-3 gap-2 mb-4">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => (
                  <button
                    key={num}
                    type="button"
                    onClick={() => { setPassword(prev => prev + num); setLoginError(false); }}
                    className="py-3 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 rounded-xl text-slate-700 font-bold text-xl transition-all border border-slate-200"
                  >
                    {num}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => { setPassword(''); setLoginError(false); }}
                  className="py-3 bg-red-50 hover:bg-red-100 active:bg-red-200 rounded-xl text-red-600 font-bold text-sm transition-all border border-red-200"
                >
                  Clear
                </button>
                <button
                  type="button"
                  onClick={() => { setPassword(prev => prev + '0'); setLoginError(false); }}
                  className="py-3 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 rounded-xl text-slate-700 font-bold text-xl transition-all border border-slate-200"
                >
                  0
                </button>
                <button
                  type="button"
                  onClick={() => { setPassword(prev => prev.slice(0, -1)); setLoginError(false); }}
                  className="py-3 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 rounded-xl text-slate-500 font-bold transition-all border border-slate-200 flex items-center justify-center"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z"></path></svg>
                </button>
              </div>

              <div className="flex gap-3 mt-2">
                <button
                  type="button"
                  onClick={() => setShowLogin(false)}
                  className="flex-1 px-4 py-3 bg-white text-slate-500 border border-slate-200 hover:bg-slate-50 hover:text-slate-700 rounded-xl font-bold transition-colors shadow-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-3 bg-blue-500 text-white hover:bg-blue-600 rounded-xl font-bold shadow-md shadow-blue-500/30 transition-all active:scale-95"
                >
                  Unlock
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Custom Confirmation Modal */}
      {confirmDialog.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 p-6 rounded-2xl shadow-xl max-w-md w-full animate-in zoom-in-95 duration-200">
            <div className="flex items-center gap-4 mb-4">
              <div className={`p-3 rounded-xl ${confirmDialog.type === 'Shutdown' ? 'bg-red-50 text-red-600 border border-red-100' : 'bg-blue-50 text-blue-600 border border-blue-100'}`}>
                {confirmDialog.type === 'Shutdown' ? (
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                ) : (
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                )}
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-800">{confirmDialog.title}</h3>
              </div>
            </div>
            <p className="text-slate-500 text-sm mb-6 ml-1">{confirmDialog.message}</p>
            <div className="flex justify-end gap-3">
              <button
                onClick={closeConfirm}
                className="px-5 py-2.5 rounded-xl font-medium text-slate-500 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmAction}
                className={`px-5 py-2.5 rounded-xl font-bold text-white shadow-md transition-all active:scale-95 ${confirmDialog.type === 'Shutdown' ? 'bg-red-500 hover:bg-red-600 shadow-red-500/30' : 'bg-blue-600 hover:bg-blue-700 shadow-blue-500/30'}`}
              >
                Yes, {confirmDialog.type}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* On-Screen Numpad Modal for Customizations */}
      {activeInput && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-200" onClick={() => setActiveInput(null)}>
          <div className="bg-white border border-slate-200 p-8 rounded-2xl shadow-xl max-w-sm w-full animate-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
            <h3 className="text-2xl font-black text-center text-slate-800 mb-2 uppercase tracking-wide">
              {activeInput.level} Grade {activeInput.field}
            </h3>

            <div className="w-full bg-slate-50 border-2 border-blue-400 rounded-xl px-4 py-4 mb-6 text-center font-black tracking-[0.1em] text-4xl shadow-inner text-slate-800 h-20 flex items-center justify-center">
              {customValues[activeInput.level][activeInput.field] || <span className="text-slate-400 opacity-50 font-medium text-2xl tracking-normal">Enter {activeInput.field}</span>}
            </div>

            <div className="grid grid-cols-3 gap-3 mb-5">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => (
                <button
                  key={num}
                  type="button"
                  onClick={() => setCustomValues(prev => ({ ...prev, [activeInput.level]: { ...prev[activeInput.level], [activeInput.field]: prev[activeInput.level][activeInput.field] + num.toString() } }))}
                  className="py-4 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 rounded-xl text-slate-800 font-bold text-2xl transition-all border border-slate-200"
                >
                  {num}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setCustomValues(prev => ({ ...prev, [activeInput.level]: { ...prev[activeInput.level], [activeInput.field]: prev[activeInput.level][activeInput.field] + '.' } }))}
                className="py-4 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 rounded-xl text-slate-800 font-black text-3xl transition-all border border-slate-200"
              >
                .
              </button>
              <button
                type="button"
                onClick={() => setCustomValues(prev => ({ ...prev, [activeInput.level]: { ...prev[activeInput.level], [activeInput.field]: prev[activeInput.level][activeInput.field] + '0' } }))}
                className="py-4 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 rounded-xl text-slate-800 font-bold text-2xl transition-all border border-slate-200"
              >
                0
              </button>
              <button
                type="button"
                onClick={() => setCustomValues(prev => ({ ...prev, [activeInput.level]: { ...prev[activeInput.level], [activeInput.field]: prev[activeInput.level][activeInput.field].slice(0, -1) } }))}
                className="py-4 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 rounded-xl text-slate-500 font-bold transition-all border border-slate-200 flex items-center justify-center"
              >
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z"></path></svg>
              </button>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setCustomValues(prev => ({ ...prev, [activeInput.level]: { ...prev[activeInput.level], [activeInput.field]: '' } }))}
                className="flex-1 py-4 bg-red-50 hover:bg-red-100 active:bg-red-200 text-red-600 rounded-xl font-bold text-xl transition-all border border-red-200"
              >
                Clear
              </button>
              <button
                type="button"
                onClick={() => setActiveInput(null)}
                className="flex-[2] py-4 bg-blue-500 hover:bg-blue-600 active:bg-blue-700 text-white rounded-xl font-black text-2xl transition-all shadow-md shadow-blue-500/30"
              >
                Enter
              </button>
            </div>

          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toast.show && (
        <div className={`fixed top-8 right-[320px] z-[100] px-6 py-3 rounded-2xl shadow-xl flex items-center gap-4 animate-in slide-in-from-top-5 fade-in duration-300 ${
          toast.type === 'error' ? 'bg-red-600 text-white shadow-red-500/30' : 
          toast.type === 'info' ? 'bg-blue-600 text-white shadow-blue-500/30' : 
          'bg-slate-800 text-white shadow-slate-800/30'
        }`}>
          {toast.type === 'error' ? (
            <svg className="w-6 h-6 text-red-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          ) : toast.type === 'info' ? (
            <svg className="w-6 h-6 text-blue-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          ) : (
            <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
          )}
          <span className="font-bold text-lg">{toast.message}</span>
        </div>
      )}

    </div>
  );
}

export default App;
