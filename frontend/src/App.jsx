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
  
  // Custom Confirmation Dialog State
  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, type: null, title: '', message: '' });

  // Login Modal State
  const [showLogin, setShowLogin] = useState(false);
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState(false);
  const [pendingPage, setPendingPage] = useState(null);

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
  const [activeTimeBelt, setActiveTimeBelt] = useState(1);
  const [timeSettingsValues, setTimeSettingsValues] = useState(["", "", "", "", "", "", ""]);
  const [activeTimeInput, setActiveTimeInput] = useState(null); // to keep track of focused input for custom numpad

  const closeConfirm = () => setConfirmDialog({ isOpen: false, type: null, title: '', message: '' });

  const handleConfirmAction = () => {
    if (confirmDialog.type === 'Shutdown') {
      handleAction('shutdown-device', 'System Shutdown');
    } else if (confirmDialog.type === 'Restart') {
      handleAction('restart-device', 'System Restart');
    }
    closeConfirm();
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
            setCustomValues(prev => ({...prev, ...res.data}));
            setSavedCustomValues(prev => ({...prev, ...res.data}));
          }
        })
        .catch(err => console.error(err));
    }
  }, [activePage]);

  useEffect(() => {
    if (activePage === 'Time Setting') {
      axios.get(`${API_URL}/time-settings/${activeTimeBelt}`)
        .then(res => setTimeSettingsValues(res.data.values))
        .catch(err => console.error(err));
    }
  }, [activePage, activeTimeBelt]);

  const saveTimeSettings = async () => {
    try {
      await axios.post(`${API_URL}/time-settings/${activeTimeBelt}`, { values: timeSettingsValues });
      alert(`Belt ${activeTimeBelt} Time Settings Saved!`);
    } catch (err) {
      console.error(err);
      alert("Failed to save time settings.");
    }
  };

  const handleTimeNumberClick = (num) => {
    if (activeTimeInput === null) return;
    setTimeSettingsValues(prev => {
      const newVals = [...prev];
      if (num === 'DEL') {
        newVals[activeTimeInput] = newVals[activeTimeInput].slice(0, -1);
      } else {
        if (newVals[activeTimeInput].length < 4) {
          newVals[activeTimeInput] += num;
        }
      }
      return newVals;
    });
  };

  const saveCustomizations = async () => {
    try {
      await axios.post(`${API_URL}/customizations`, { values: customValues });
      setSavedCustomValues(customValues);
      alert("Values saved successfully!");
    } catch (err) {
      console.error(err);
      alert("Failed to save values. Ensure backend is running.");
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
    <div className="h-screen w-screen bg-[#FDFBF7] text-[#3b352b] font-sans flex overflow-hidden selection:bg-orange-500/30">
      
      {/* Decorative Background Blob - Cream/Orange/Blue Theme */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
        <div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] bg-orange-300/10 blur-[120px] rounded-full mix-blend-multiply"></div>
        <div className="absolute top-[60%] -right-[10%] w-[40%] h-[50%] bg-blue-300/15 blur-[120px] rounded-full mix-blend-multiply"></div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col p-6 pt-4 z-10 min-w-0">
        
        {/* GLOBAL TOP BAR */}
        <div className="flex justify-between items-center mb-8 shrink-0 px-2 pb-4 border-b border-[#efece3]">
          {/* Company Branding (Left) */}
          <div className="flex items-center gap-5">
            <div className="relative flex items-center justify-center">
              {/* Outer decorative ring */}
              <div className="absolute inset-0 rounded-full border border-orange-500/20 scale-[1.15]"></div>
              <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-lg shadow-blue-900/10 overflow-hidden relative ring-4 ring-white z-10">
                 <img src="/video.gif" alt="Logo" className="absolute w-full h-full object-cover scale-[1.35]" />
              </div>
            </div>
            <div className="flex flex-col justify-center">
              <h1 className="text-4xl font-extrabold tracking-tight text-slate-800 leading-none flex items-baseline gap-1.5">
                Keya <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-500 to-amber-500">Fusion</span>
              </h1>
              <div className="flex items-center gap-2 mt-1.5">
                <div className="h-[1px] w-6 bg-blue-500/30"></div>
                <p className="text-blue-600 text-[11px] font-bold tracking-[0.3em] uppercase leading-none">Technology</p>
              </div>
            </div>
          </div>

          {/* Dynamic Page Title (Right) */}
          <div className="flex flex-col items-end text-right">
             <h2 className="text-4xl font-extrabold tracking-tight text-[#2d2820] drop-shadow-sm flex items-center gap-3">
               {activePage === 'Control Hub' && "System Control Hub"}
               {activePage === 'Air Valve' && (
                 <>
                  <div className="p-1.5 bg-orange-100 rounded-xl text-orange-600">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                  </div>
                  Air Valve Testing
                 </>
               )}
               {activePage !== 'Control Hub' && activePage !== 'Air Valve' && activePage}
             </h2>
             <p className="text-[#8a8174] text-base mt-2">
               {activePage === 'Control Hub' && "Manage Python automation, grading scripts, and real-time operations."}
               {activePage === 'Air Valve' && "Manual testing interface for 15 belts and their respective 7 ports."}
             </p>
          </div>
        </div>
        
        {/* Render Control Hub */}
        {activePage === 'Control Hub' ? (
          <div className="flex flex-col h-full w-full max-w-[1600px] mx-auto animate-in fade-in duration-500">
            
            {/* Main Layout Row */}
            <div className="flex flex-1 gap-6 min-h-0">
              
              {/* GRAPH AREA (Left/Middle) */}
              <div className="flex-1 bg-white/70 backdrop-blur-xl rounded-3xl border border-[#efece3] p-6 shadow-xl flex flex-col relative overflow-hidden group">
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-orange-400 to-blue-400 opacity-80"></div>
                  
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="text-xl font-bold text-[#2d2820] flex items-center gap-2">
                      <svg className="w-5 h-5 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"></path></svg>
                      Live Grading Analytics
                    </h3>
                    <div className="px-3 py-1 bg-[#f6f2e6] text-xs font-semibold rounded-full border border-[#efece3] text-[#8a8174]">Waiting for Data</div>
                  </div>

                  {/* Live Animated Bar Chart */}
                  <div className="flex-1 rounded-2xl flex flex-col items-center justify-center transition-colors">
                     {graphData.length > 0 ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={graphData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e8e4d9" vertical={false} />
                            <XAxis dataKey="name" stroke="#a69f91" tick={{ fill: '#a69f91' }} tickLine={false} axisLine={false} />
                            <YAxis stroke="#a69f91" tick={{ fill: '#a69f91' }} tickLine={false} axisLine={false} allowDecimals={false} />
                            <Tooltip 
                              cursor={{fill: '#fcfaf5', opacity: 0.8}}
                              contentStyle={{ backgroundColor: '#ffffff', borderColor: '#efece3', borderRadius: '12px', color: '#2d2820', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.05)' }}
                              itemStyle={{ color: '#2d2820' }}
                            />
                            <Bar dataKey="count" radius={[6, 6, 0, 0]} animationDuration={1000}>
                              {graphData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                     ) : (
                        <div className="flex flex-col items-center justify-center text-[#a69f91]">
                          <svg className="w-10 h-10 mb-2 animate-spin text-[#d4cdbd]" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                          Connecting to Data Stream...
                        </div>
                     )}
                  </div>
              </div>

              {/* CONTROLS SIDEBAR (Right side of content area) */}
              <div className="w-[340px] flex flex-col gap-6 h-full">
                
                {/* Control Panel */}
                <div className="bg-white/70 backdrop-blur-xl p-5 rounded-3xl border border-[#efece3] shadow-xl flex flex-col flex-1">
                  <h3 className="text-lg font-bold text-[#2d2820] mb-5 px-2 flex items-center gap-2">
                    <svg className="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
                    Action Commands
                  </h3>

                  <div className="flex flex-col gap-3">
                    <button 
                      onClick={() => handleAction('run-default', 'Default Mode')}
                      className={`group relative w-full p-4 rounded-2xl transition-all active:scale-[0.98] flex items-center gap-4 border overflow-hidden ${currentMode === 'Default Mode' ? 'bg-emerald-50 border-emerald-500 shadow-md ring-2 ring-emerald-500/20' : 'bg-white hover:bg-[#fcfaf5] border-[#efece3] hover:border-emerald-300 shadow-sm hover:shadow-md text-[#3b352b]'}`}
                    >
                      <div className="w-10 h-10 rounded-xl bg-emerald-50 group-hover:bg-emerald-100 flex items-center justify-center transition-colors">
                         <svg className="w-5 h-5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
                            {currentMode === 'Default Mode' ? (
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path>
                            ) : (
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd"></path>
                            )}
                         </svg>
                      </div>
                      <div className="text-left">
                        <span className="block text-base font-bold text-[#2d2820]">Default Mode</span>
                        <span className="block text-xs text-[#8a8174] group-hover:text-emerald-700 transition-colors">Run standard sequence</span>
                      </div>
                    </button>
                    
                    <button 
                      onClick={() => handleAction('run-grading', 'Grading Mode')}
                      className={`group relative w-full p-4 rounded-2xl transition-all active:scale-[0.98] flex items-center gap-4 border overflow-hidden ${currentMode === 'Grading Mode' ? 'bg-blue-50 border-blue-500 shadow-md ring-2 ring-blue-500/20' : 'bg-white hover:bg-[#fcfaf5] border-[#efece3] hover:border-blue-300 shadow-sm hover:shadow-md text-[#3b352b]'}`}
                    >
                      <div className="w-10 h-10 rounded-xl bg-blue-50 group-hover:bg-blue-100 flex items-center justify-center transition-colors">
                         <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                            {currentMode === 'Grading Mode' ? (
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path>
                            ) : (
                              <path d="M5 4a1 1 0 00-2 0v7.268a2 2 0 000 3.464V16a1 1 0 102 0v-1.268a2 2 0 000-3.464V4zM11 4a1 1 0 10-2 0v1.268a2 2 0 000 3.464V16a1 1 0 102 0V8.732a2 2 0 000-3.464V4zM16 3a1 1 0 011 1v7.268a2 2 0 010 3.464V16a1 1 0 11-2 0v-1.268a2 2 0 010-3.464V4a1 1 0 011-1z"></path>
                            )}
                         </svg>
                      </div>
                      <div className="text-left">
                        <span className="block text-base font-bold text-[#2d2820]">Grading Mode</span>
                        <span className="block text-xs text-[#8a8174] group-hover:text-blue-700 transition-colors">Run grading scripts</span>
                      </div>
                    </button>

                    <button 
                      onClick={() => handleAction('run-color', 'Color Grading Mode')}
                      className={`group relative w-full p-4 rounded-2xl transition-all active:scale-[0.98] flex items-center gap-4 border overflow-hidden ${currentMode === 'Color Grading Mode' ? 'bg-purple-50 border-purple-500 shadow-md ring-2 ring-purple-500/20' : 'bg-white hover:bg-[#fcfaf5] border-[#efece3] hover:border-purple-300 shadow-sm hover:shadow-md text-[#3b352b]'}`}
                    >
                      <div className="w-10 h-10 rounded-xl bg-purple-50 group-hover:bg-purple-100 flex items-center justify-center transition-colors">
                         <svg className="w-5 h-5 text-purple-600" fill="currentColor" viewBox="0 0 20 20">
                            {currentMode === 'Color Grading Mode' ? (
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path>
                            ) : (
                              <path fillRule="evenodd" d="M4 2a2 2 0 00-2 2v11a3 3 0 106 0V4a2 2 0 00-2-2H4zm1 14a1 1 0 100-2 1 1 0 000 2zm5-1.757l4.9-4.9a2 2 0 000-2.828L13.485 5.1a2 2 0 00-2.828 0L10 5.757v8.486zM16 18H9.071l6-6H16a2 2 0 012 2v2a2 2 0 01-2 2z" clipRule="evenodd"></path>
                            )}
                         </svg>
                      </div>
                      <div className="text-left">
                        <span className="block text-base font-bold text-[#2d2820]">Color Grading</span>
                        <span className="block text-xs text-[#8a8174] group-hover:text-purple-700 transition-colors">Run color scripts</span>
                      </div>
                    </button>
                  </div>

                  <div className="mt-auto pt-4">
                    <button 
                      onClick={() => handleAction('stop-all', 'Stop All')}
                      className="w-full p-4 bg-red-50/80 hover:bg-red-500 text-red-600 hover:text-white font-bold text-sm uppercase tracking-wider rounded-2xl transition-all active:scale-[0.98] border border-red-200 hover:border-red-500 hover:shadow-lg flex justify-center items-center gap-2"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path></svg>
                      Emergency Stop All
                    </button>
                  </div>

                </div>

                {/* Status Console Mini */}
                <div className="bg-[#f6f2e6]/60 p-4 rounded-3xl border border-[#efece3] shadow-sm backdrop-blur-sm">
                  <div className="flex items-center gap-2 mb-2">
                     <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                     <span className="font-semibold text-[#8a8174] text-xs uppercase tracking-wider">System Terminal</span>
                  </div>
                  <div className="font-mono text-xs text-[#5c5549] bg-white p-3 rounded-xl border border-[#efece3] overflow-hidden text-ellipsis whitespace-nowrap shadow-inner">
                    &gt; {status}
                  </div>
                </div>

              </div>
            </div>
          </div>
        ) : activePage === 'Air Valve' ? (
          <div className="flex flex-col h-full w-full max-w-[1600px] mx-auto animate-in fade-in duration-500 overflow-hidden">

            <div className="flex-1 bg-white/70 backdrop-blur-xl border border-[#efece3] rounded-3xl p-6 shadow-xl flex flex-col overflow-hidden">
              
              {/* Pagination Tabs */}
              <div className="flex gap-3 mb-6 justify-center shrink-0">
                {[1, 2, 3].map(pageNum => (
                  <button 
                    key={pageNum}
                    onClick={() => setAirValvePage(pageNum)}
                    className={`px-8 py-3 rounded-2xl font-bold text-lg transition-all border ${
                      airValvePage === pageNum 
                        ? 'bg-orange-500 text-white border-orange-600 shadow-md shadow-orange-500/30' 
                        : 'bg-white text-[#8a8174] border-[#efece3] hover:border-orange-300 hover:text-orange-600 hover:bg-orange-50'
                    }`}
                  >
                    Page {pageNum} <span className="text-sm font-medium opacity-80 ml-1">(Belts {(pageNum-1)*5 + 1}-{pageNum*5})</span>
                  </button>
                ))}
              </div>

              <div className="flex-1 flex flex-col min-h-0">
                <div className="flex-1 flex flex-col gap-3 h-full">
                  {Array.from({ length: 5 }, (_, i) => (airValvePage - 1) * 5 + i + 1).map(beltId => (
                    <div key={beltId} className="flex-1 flex items-center gap-4 p-3 bg-[#fbf9f4] border border-[#efece3] rounded-3xl hover:border-orange-300 hover:shadow-md transition-all group min-h-0">
                      <div className="w-32 xl:w-40 h-full font-black text-[#2d2820] text-2xl xl:text-3xl bg-white rounded-2xl border border-[#efece3] flex items-center justify-center shadow-sm group-hover:border-orange-400 group-hover:text-orange-700 transition-colors shrink-0">
                        Belt {beltId}
                      </div>
                      <div className="flex gap-3 flex-1 h-full">
                        {[11, 12, 13, 14, 15, 16, 21].map(portId => (
                          <button
                            key={portId}
                            onClick={async (e) => {
                              const btn = e.currentTarget;
                              btn.classList.add('bg-orange-400', 'text-white', 'border-orange-500', 'shadow-inner');
                              btn.classList.remove('bg-white', 'text-[#5c5549]', 'border-[#efece3]', 'hover:border-orange-400', 'hover:text-orange-600');
                              setTimeout(() => {
                                btn.classList.remove('bg-orange-400', 'text-white', 'border-orange-500', 'shadow-inner');
                                btn.classList.add('bg-white', 'text-[#5c5549]', 'border-[#efece3]', 'hover:border-orange-400', 'hover:text-orange-600');
                              }, 300);
                              
                              try {
                                await axios.post(`${API_URL}/fire-valve`, { belt_id: beltId, port_id: portId });
                              } catch (err) {
                                console.error(err);
                              }
                            }}
                            className="flex-1 h-full rounded-2xl font-black text-2xl xl:text-3xl text-[#5c5549] bg-white border-[3px] border-[#efece3] shadow-sm hover:border-orange-400 hover:text-orange-600 transition-all active:scale-[0.95] flex items-center justify-center focus:outline-none select-none"
                          >
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
          <div className="flex flex-col h-full w-full max-w-[1600px] mx-auto animate-in fade-in duration-500 overflow-hidden">
            <div className="flex-1 flex gap-8 overflow-hidden">
              
              {/* Left Side: Input Form */}
              <div className="flex-1 flex flex-col bg-white/70 backdrop-blur-xl border border-[#efece3] p-6 rounded-3xl shadow-xl">
                
                <div className="flex gap-4 px-4 mb-2 text-[#8a8174] font-bold text-sm tracking-wider uppercase shrink-0">
                  <div className="w-24 text-center">Grade</div>
                  <div className="flex-1 text-center">Min Value</div>
                  <div className="flex-1 text-center">Max Value</div>
                </div>

                <div className="flex flex-col gap-5 flex-1 px-4 mb-4">
                  {['400', '320', '240', '210', '180'].map(level => (
                    <div key={level} className="flex gap-6 items-center flex-1 min-h-0">
                      <div className="w-24 h-full text-center font-black text-2xl text-[#3b352b] bg-[#f6f2e6] border border-[#efece3] rounded-xl flex items-center justify-center shrink-0">{level}</div>
                      <div className="flex-1 h-full">
                        <input 
                          type="text"
                          readOnly
                          value={customValues[level].min}
                          onClick={() => setActiveInput({level, field: 'min'})}
                          placeholder="Min"
                          className="w-full h-full bg-white border-[2px] border-[#efece3] rounded-xl px-4 text-center font-bold text-2xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm transition-all cursor-pointer"
                        />
                      </div>
                      <div className="flex-1 h-full">
                        <input 
                          type="text"
                          readOnly
                          value={customValues[level].max}
                          onClick={() => setActiveInput({level, field: 'max'})}
                          placeholder="Max"
                          className="w-full h-full bg-white border-[2px] border-[#efece3] rounded-xl px-4 text-center font-bold text-2xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm transition-all cursor-pointer"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right Side: Display Values & OK Button */}
              <div className="w-[280px] flex flex-col gap-6 shrink-0 h-full">
                
                {/* Display Screen */}
                <div className="flex-1 flex flex-col bg-[#2d2820] text-[#fdfbf7] p-5 rounded-3xl shadow-xl relative overflow-hidden min-h-0">
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-orange-500 to-blue-500"></div>
                  <h3 className="text-sm font-bold text-orange-400 mb-5 uppercase tracking-wider flex items-center justify-center gap-1.5 text-center shrink-0">
                    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    Saved Data
                  </h3>

                  <div className="flex flex-col gap-2 flex-1 overflow-y-auto pr-1">
                    {['400', '320', '240', '210', '180'].map(level => (
                      <div key={`saved-${level}`} className="flex justify-between items-center border-b border-[#5c5549] pb-2 last:border-0">
                        <span className="font-black text-xl text-white">{level}</span>
                        <div className="flex gap-3">
                          <div className="flex flex-col items-end">
                             <span className="text-[9px] text-[#a69f91] uppercase tracking-wider mb-0.5">Min</span>
                             <span className="font-mono font-bold text-blue-400 text-sm">{savedCustomValues[level].min || '--'}</span>
                          </div>
                          <div className="flex flex-col items-end">
                             <span className="text-[9px] text-[#a69f91] uppercase tracking-wider mb-0.5">Max</span>
                             <span className="font-mono font-bold text-orange-400 text-sm">{savedCustomValues[level].max || '--'}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* OK Button */}
                <button 
                  onClick={saveCustomizations}
                  className="w-full h-32 bg-orange-500 hover:bg-orange-600 text-white rounded-3xl font-black text-4xl shadow-xl shadow-orange-500/30 transition-all active:scale-[0.98] flex justify-center items-center gap-3 border-2 border-orange-600 shrink-0"
                >
                  <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7"></path></svg>
                  OK
                </button>

              </div>

            </div>
          </div>
        ) : activePage === 'Settings' ? (
          <div className="flex h-full w-full gap-6 max-w-[1600px] mx-auto animate-in fade-in duration-500">
            {/* Left side content placeholder */}
            <div className="flex-1 bg-white/70 backdrop-blur-xl border border-[#efece3] rounded-3xl p-8 shadow-xl flex flex-col items-center justify-center">
               <div className="w-24 h-24 bg-[#f6f2e6] rounded-full flex items-center justify-center mb-6 border border-[#efece3]">
                  <svg className="w-12 h-12 text-[#b8b0a1]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
               </div>
               <h2 className="text-3xl font-bold text-[#2d2820] mb-2">System Settings</h2>
               <p className="text-[#8a8174]">Select a configuration module from the right panel.</p>
            </div>

            {/* Right side buttons */}
            <div className="w-[340px] flex flex-col gap-6 h-full">
              <div className="bg-white/70 backdrop-blur-xl p-5 rounded-3xl border border-[#efece3] shadow-xl flex flex-col flex-1">
                <h3 className="text-lg font-bold text-[#2d2820] mb-6 px-2 flex items-center gap-2">
                  <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
                  Configurations
                </h3>
                
                <div className="flex flex-col gap-4">
                  {/* Time Setting Button */}
                  <button onClick={() => setActivePage('Time Setting')} className="group relative w-full p-5 bg-white hover:bg-indigo-50 text-[#3b352b] rounded-2xl shadow-sm hover:shadow-md transition-all active:scale-[0.98] flex items-center gap-4 border border-[#efece3] hover:border-indigo-300">
                    <div className="w-12 h-12 rounded-xl bg-indigo-50 group-hover:bg-indigo-100 flex items-center justify-center transition-colors shrink-0">
                      <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </div>
                    <span className="text-lg font-bold text-[#2d2820] text-left">Time Setting</span>
                  </button>

                  {/* Camera Button */}
                  <button className="group relative w-full p-5 bg-white hover:bg-sky-50 text-[#3b352b] rounded-2xl shadow-sm hover:shadow-md transition-all active:scale-[0.98] flex items-center gap-4 border border-[#efece3] hover:border-sky-300">
                    <div className="w-12 h-12 rounded-xl bg-sky-50 group-hover:bg-sky-100 flex items-center justify-center transition-colors shrink-0">
                      <svg className="w-6 h-6 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                    </div>
                    <span className="text-lg font-bold text-[#2d2820] text-left">Camera</span>
                  </button>

                  {/* Comports Button */}
                  <button className="group relative w-full p-5 bg-white hover:bg-amber-50 text-[#3b352b] rounded-2xl shadow-sm hover:shadow-md transition-all active:scale-[0.98] flex items-center gap-4 border border-[#efece3] hover:border-amber-300">
                    <div className="w-12 h-12 rounded-xl bg-amber-50 group-hover:bg-amber-100 flex items-center justify-center transition-colors shrink-0">
                      <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                    </div>
                    <span className="text-lg font-bold text-[#2d2820] text-left">Comports</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : activePage === 'Time Setting' ? (
          <div className="flex h-full w-full gap-6 max-w-[1600px] mx-auto animate-in fade-in duration-500">

            {/* Main Area (Matrix of 15 belts x 7 boxes) */}
            <div className="flex-1 flex flex-col bg-white/70 backdrop-blur-xl border border-[#efece3] rounded-3xl p-6 shadow-xl min-w-0">
              <div className="flex justify-between items-center mb-4 shrink-0">
                <h2 className="text-3xl font-extrabold text-[#2d2820]">
                  Time Setting <span className="text-indigo-500">Matrix</span>
                </h2>
                <div className="flex gap-4">
                  <button 
                    onClick={applyToAllBelts}
                    className="px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white rounded-2xl font-bold shadow-lg shadow-amber-500/30 transition-all active:scale-95 flex items-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                    Apply Belt 1 to All
                  </button>
                  <button 
                    onClick={saveTimeSettings}
                    className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-bold shadow-lg shadow-indigo-500/30 transition-all active:scale-95 flex items-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                    Save All Settings
                  </button>
                </div>
              </div>

              {/* Scrollable Matrix Table */}
              <div className="flex-1 overflow-y-auto custom-scrollbar border border-[#efece3] rounded-2xl bg-[#fbf9f4]">
                <table className="w-full text-center border-collapse">
                  <thead className="sticky top-0 bg-[#f6f2e6] shadow-sm z-10">
                    <tr>
                      <th className="p-4 text-slate-500 font-bold border-b border-[#efece3]">BELT</th>
                      {[...Array(7)].map((_, i) => (
                        <th key={i} className="p-4 text-slate-500 font-bold border-b border-[#efece3]">BOX {i + 1}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...Array(15)].map((_, r) => {
                      const beltId = (r + 1).toString();
                      return (
                        <tr key={beltId} className="hover:bg-white transition-colors border-b border-[#efece3]/50">
                          <td className="p-3 font-black text-slate-700 bg-white/50">{beltId}</td>
                          {[...Array(7)].map((_, c) => {
                            const isSelected = activeTimeInput && activeTimeInput.belt === beltId && activeTimeInput.idx === c;
                            const val = timeSettingsValues[beltId]?.[c];
                            return (
                              <td key={c} className="p-2">
                                <div 
                                  onClick={() => setActiveTimeInput({ belt: beltId, idx: c })}
                                  className={`h-12 flex items-center justify-center text-xl font-bold rounded-xl cursor-pointer transition-all border-2
                                    ${isSelected ? 'bg-indigo-50 border-indigo-500 text-indigo-700 shadow-inner scale-[1.03]' : 'bg-white border-[#e5e0d8] text-[#2d2820] hover:border-indigo-300'}
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
                <div className="bg-white/70 backdrop-blur-xl border border-[#efece3] rounded-3xl p-5 shadow-xl">
                  <h3 className="text-sm font-bold text-slate-400 tracking-widest text-center mb-4">NUMPAD</h3>
                  <div className="grid grid-cols-3 gap-3">
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, '.', 0, 'DEL'].map((num) => (
                      <button
                        key={num}
                        onClick={() => handleTimeNumberClick(num)}
                        disabled={num === '.'}
                        className={`h-16 rounded-2xl font-black text-2xl transition-all active:scale-95 flex justify-center items-center shadow-sm
                          ${num === 'DEL' ? 'bg-red-50 text-red-600 hover:bg-red-100' : 
                            num === '.' ? 'bg-gray-100 text-gray-300 cursor-not-allowed' : 
                            'bg-white text-[#2d2820] border-2 border-[#efece3] hover:border-indigo-300 hover:text-indigo-600'}
                        `}
                      >
                        {num === 'DEL' ? (
                          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z"></path></svg>
                        ) : num}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
          </div>
        ) : (
          /* Render Other Pages */
          <div className="flex-1 flex flex-col items-center justify-center border border-dashed border-[#d4cdbd] rounded-3xl bg-white/40 backdrop-blur-sm animate-in fade-in duration-500">
             <div className="w-20 h-20 bg-[#f6f2e6] rounded-full flex items-center justify-center mb-6 border border-[#efece3]">
                <svg className="w-10 h-10 text-[#b8b0a1]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
             </div>
             <h2 className="text-3xl font-bold text-[#2d2820] mb-2">{activePage}</h2>
             <p className="text-[#8a8174]">This module is currently under construction.</p>
          </div>
        )}

      </div>
      
      {/* RIGHT SIDE MAIN NAVBAR */}
      <div className="w-[300px] bg-[#fbf9f4]/95 backdrop-blur-2xl border-l border-[#efece3] p-6 flex flex-col shadow-[-10px_0_40px_rgba(0,0,0,0.03)] z-20">

        {/* Live Date/Time Display */}
        <div className="flex flex-col items-center w-full border-b border-[#efece3] pb-6 mb-6 mt-2">
           <span className="text-3xl font-bold text-[#3b352b] tabular-nums tracking-tight">
             {currentDateTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
           </span>
           <span className="text-xs font-bold text-orange-500/80 uppercase tracking-wider mt-1.5">
             {currentDateTime.toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric' })}
           </span>
        </div>

        <nav className="flex flex-col gap-3 flex-1">
          {/* Main Pages */}
          <div className="flex flex-col gap-2">
            {navItems.filter(item => item.type === 'page').map(page => {
              const isActive = activePage === page.name;
              return (
                <button 
                  key={page.name}
                  onClick={() => handleNavClick(page)}
                  className={`group w-full flex items-center justify-start gap-4 px-4 py-3.5 rounded-2xl font-bold transition-all duration-300 ${
                    isActive 
                      ? 'bg-white text-orange-600 shadow-md border border-orange-100 translate-x-1' 
                      : 'bg-transparent text-[#8a8174] hover:bg-white hover:text-[#3b352b] border border-transparent hover:shadow-sm'
                  }`}
                >
                  <div className={`p-2.5 rounded-xl transition-colors ${isActive ? 'bg-orange-100 text-orange-600' : 'bg-[#f6f2e6] text-[#a69f91] group-hover:bg-[#efece3] group-hover:text-[#5c5549]'}`}>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={page.icon}></path>
                    </svg>
                  </div>
                  <span className="text-base">{page.name}</span>
                </button>
              )
            })}
          </div>
          
          <div className="h-px w-full bg-[#efece3] my-4"></div>

          {/* Action Buttons */}
          <div className="flex flex-col gap-3 mt-auto">
            {navItems.filter(item => item.type === 'action').map(action => {
              const isRed = action.color === 'red';
              const textClass = isRed ? 'text-red-600' : 'text-orange-500';
              const bgClass = isRed ? 'hover:bg-red-50' : 'hover:bg-orange-50';
              const borderHoverClass = isRed ? 'hover:border-red-100' : 'hover:border-orange-100';
              const iconBgClass = isRed ? 'bg-red-50' : 'bg-orange-50';
              const iconGroupHoverClass = isRed ? 'group-hover:bg-red-100' : 'group-hover:bg-orange-100';
              
              return (
                <button 
                  key={action.name}
                  onClick={() => handleNavClick(action)}
                  className={`group w-full flex items-center justify-start gap-4 px-4 py-3.5 rounded-2xl font-bold transition-all duration-300 bg-transparent ${textClass} ${bgClass} border border-transparent ${borderHoverClass} hover:shadow-sm`}
                >
                  <div className={`p-2.5 rounded-xl transition-colors ${iconBgClass} ${textClass} ${iconGroupHoverClass}`}>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={action.icon}></path>
                    </svg>
                  </div>
                  <span className="text-base">{action.name}</span>
                </button>
              )
            })}
          </div>
        </nav>
      </div>

      {/* Login Password Modal */}
      {showLogin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#2d2820]/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#fdfbf7] border border-[#efece3] p-8 rounded-3xl shadow-2xl max-w-sm w-full animate-in zoom-in-95 duration-200">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center shadow-inner">
                 <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
              </div>
            </div>
            <h3 className="text-2xl font-black text-center text-[#2d2820] mb-2">Restricted Access</h3>
            <p className="text-center text-[#8a8174] text-sm mb-6">Enter administrator password to access {pendingPage}.</p>
            
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
                className={`w-full px-4 py-3 rounded-xl border ${loginError ? 'border-red-500 bg-red-50 text-red-700' : 'border-[#efece3] bg-white text-[#2d2820]'} focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all mb-4 text-center font-black tracking-[0.3em] text-2xl shadow-sm`}
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
                    className="py-3 bg-[#fbf9f4] hover:bg-[#efece3] active:bg-[#e2ddd0] rounded-xl text-[#3b352b] font-bold text-xl transition-all border border-[#efece3]"
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
                  className="py-3 bg-[#fbf9f4] hover:bg-[#efece3] active:bg-[#e2ddd0] rounded-xl text-[#3b352b] font-bold text-xl transition-all border border-[#efece3]"
                >
                  0
                </button>
                <button
                  type="button"
                  onClick={() => { setPassword(prev => prev.slice(0, -1)); setLoginError(false); }}
                  className="py-3 bg-[#fbf9f4] hover:bg-[#efece3] active:bg-[#e2ddd0] rounded-xl text-[#5c5549] font-bold transition-all border border-[#efece3] flex items-center justify-center"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z"></path></svg>
                </button>
              </div>
              
              <div className="flex gap-3 mt-2">
                <button 
                  type="button" 
                  onClick={() => setShowLogin(false)}
                  className="flex-1 px-4 py-3 bg-white text-[#8a8174] border border-[#efece3] hover:bg-[#fbf9f4] hover:text-[#5c5549] rounded-xl font-bold transition-colors shadow-sm"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#2d2820]/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#fdfbf7] border border-[#efece3] p-6 rounded-3xl shadow-2xl max-w-md w-full animate-in zoom-in-95 duration-200">
            <div className="flex items-center gap-4 mb-4">
              <div className={`p-3 rounded-2xl ${confirmDialog.type === 'Shutdown' ? 'bg-red-100 text-red-600' : 'bg-orange-100 text-orange-600'}`}>
                {confirmDialog.type === 'Shutdown' ? (
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                ) : (
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                )}
              </div>
              <div>
                <h3 className="text-xl font-bold text-[#2d2820]">{confirmDialog.title}</h3>
              </div>
            </div>
            <p className="text-[#5c5549] text-sm mb-6 ml-1">{confirmDialog.message}</p>
            <div className="flex justify-end gap-3">
              <button 
                onClick={closeConfirm}
                className="px-5 py-2.5 rounded-xl font-medium text-[#5c5549] hover:bg-[#efece3] transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleConfirmAction}
                className={`px-5 py-2.5 rounded-xl font-bold text-white shadow-md transition-all active:scale-95 ${confirmDialog.type === 'Shutdown' ? 'bg-red-500 hover:bg-red-600 shadow-red-500/30' : 'bg-orange-500 hover:bg-orange-600 shadow-orange-500/30'}`}
              >
                Yes, {confirmDialog.type}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* On-Screen Numpad Modal for Customizations */}
      {activeInput && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[#2d2820]/40 backdrop-blur-sm animate-in fade-in duration-200" onClick={() => setActiveInput(null)}>
          <div className="bg-[#fdfbf7] border border-[#efece3] p-8 rounded-3xl shadow-2xl max-w-sm w-full animate-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
            <h3 className="text-2xl font-black text-center text-[#2d2820] mb-2 uppercase tracking-wide">
              {activeInput.level} Grade {activeInput.field}
            </h3>
            
            <div className="w-full bg-white border-[3px] border-blue-400 rounded-xl px-4 py-4 mb-6 text-center font-black tracking-[0.1em] text-4xl shadow-inner text-[#3b352b] h-20 flex items-center justify-center">
              {customValues[activeInput.level][activeInput.field] || <span className="text-[#a69f91] opacity-50 font-medium text-2xl tracking-normal">Enter {activeInput.field}</span>}
            </div>

            <div className="grid grid-cols-3 gap-3 mb-5">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => (
                <button
                  key={num}
                  type="button"
                  onClick={() => setCustomValues(prev => ({...prev, [activeInput.level]: {...prev[activeInput.level], [activeInput.field]: prev[activeInput.level][activeInput.field] + num.toString()}}))}
                  className="py-4 bg-[#fbf9f4] hover:bg-[#efece3] active:bg-[#e2ddd0] rounded-xl text-[#3b352b] font-bold text-2xl transition-all border border-[#efece3]"
                >
                  {num}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setCustomValues(prev => ({...prev, [activeInput.level]: {...prev[activeInput.level], [activeInput.field]: prev[activeInput.level][activeInput.field] + '.'}}))}
                className="py-4 bg-[#fbf9f4] hover:bg-[#efece3] active:bg-[#e2ddd0] rounded-xl text-[#3b352b] font-black text-3xl transition-all border border-[#efece3]"
              >
                .
              </button>
              <button
                type="button"
                onClick={() => setCustomValues(prev => ({...prev, [activeInput.level]: {...prev[activeInput.level], [activeInput.field]: prev[activeInput.level][activeInput.field] + '0'}}))}
                className="py-4 bg-[#fbf9f4] hover:bg-[#efece3] active:bg-[#e2ddd0] rounded-xl text-[#3b352b] font-bold text-2xl transition-all border border-[#efece3]"
              >
                0
              </button>
              <button
                type="button"
                onClick={() => setCustomValues(prev => ({...prev, [activeInput.level]: {...prev[activeInput.level], [activeInput.field]: prev[activeInput.level][activeInput.field].slice(0, -1)}}))}
                className="py-4 bg-[#fbf9f4] hover:bg-[#efece3] active:bg-[#e2ddd0] rounded-xl text-[#5c5549] font-bold transition-all border border-[#efece3] flex items-center justify-center"
              >
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z"></path></svg>
              </button>
            </div>
            
            <div className="flex gap-3">
              <button 
                type="button"
                onClick={() => setCustomValues(prev => ({...prev, [activeInput.level]: {...prev[activeInput.level], [activeInput.field]: ''}}))}
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

    </div>
  );
}

export default App;
