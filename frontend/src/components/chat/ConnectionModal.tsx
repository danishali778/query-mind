import { useState } from 'react';
import * as api from '../../services/api';

interface ConnectionModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConnected: () => void;
}

export function ConnectionModal({ isOpen, onClose, onConnected }: ConnectionModalProps) {
    const [host, setHost] = useState('localhost');
    const [port, setPort] = useState('5432');
    const [database, setDatabase] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [testing, setTesting] = useState(false);
    const [connecting, setConnecting] = useState(false);
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

    if (!isOpen) return null;

    const getConfig = () => ({
        db_type: 'postgresql' as const,
        host,
        port: parseInt(port),
        database,
        username,
        password,
    });

    const handleTest = async () => {
        setTesting(true);
        setTestResult(null);
        try {
            const result = await api.testConnection(getConfig());
            setTestResult({ success: result.success, message: result.message });
        } catch (err) {
            setTestResult({ success: false, message: err instanceof Error ? err.message : 'Test failed' });
        } finally {
            setTesting(false);
        }
    };

    const handleConnect = async () => {
        setConnecting(true);
        setTestResult(null);
        try {
            await api.connectDatabase(getConfig());
            setTestResult({ success: true, message: 'Connected successfully!' });
            setTimeout(() => {
                onConnected();
                onClose();
                // Reset form
                setDatabase('');
                setUsername('');
                setPassword('');
                setTestResult(null);
            }, 800);
        } catch (err) {
            setTestResult({ success: false, message: err instanceof Error ? err.message : 'Connection failed' });
        } finally {
            setConnecting(false);
        }
    };

    const postgresOnly = true;

    const inputStyle = {
        width: '100%', padding: '12px 16px', background: '#fff', border: '1.5px solid #e8e4dc', borderRadius: 12,
        fontFamily: "'DM Sans', sans-serif", fontSize: '0.9rem', color: '#1e1e2e', outline: 'none',
        transition: 'border-color 0.2s, box-shadow 0.2s', boxSizing: 'border-box' as const,
    };

    const labelStyle = {
        fontFamily: "'DM Sans', sans-serif", fontSize: '0.82rem', fontWeight: 600 as const, color: '#4a4b58',
        marginBottom: 6, display: 'block' as const,
    };

    return (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {/* Backdrop */}
            <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.3)', backdropFilter: 'blur(4px)' }} />

            {/* Modal */}
            <div style={{ position: 'relative', width: 520, maxHeight: '90vh', overflowY: 'auto', background: '#faf8f5', borderRadius: 20, boxShadow: '0 20px 60px rgba(0,0,0,0.12)', padding: '32px 36px', border: '1px solid #e8e4dc' }}>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
                    <div>
                        <h3 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: '1.25rem', color: '#1e1e2e', margin: 0, fontStyle: 'normal' }}>
                            Connect Database
                        </h3>
                        <p style={{ fontSize: '0.85rem', color: '#9b9da8', margin: '6px 0 0', fontWeight: 400 }}>
                            Enter your database credentials below
                        </p>
                    </div>
                    <button onClick={onClose} style={{ width: 36, height: 36, borderRadius: 10, border: '1px solid #e8e4dc', background: '#fff', color: '#9b9da8', fontSize: '1.1rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        ✕
                    </button>
                </div>


                {/* Form Fields */}
                {postgresOnly && (
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14, marginBottom: 14 }}>
                        <div>
                            <label style={labelStyle}>Host</label>
                            <input value={host} onChange={e => setHost(e.target.value)} placeholder="localhost" style={inputStyle}
                                onFocus={e => { e.target.style.borderColor = '#6c5ce7'; e.target.style.boxShadow = '0 0 0 3px rgba(108,92,231,0.1)'; }}
                                onBlur={e => { e.target.style.borderColor = '#e8e4dc'; e.target.style.boxShadow = 'none'; }}
                            />
                        </div>
                        <div>
                            <label style={labelStyle}>Port</label>
                            <input value={port} onChange={e => setPort(e.target.value)} placeholder="5432" style={inputStyle}
                                onFocus={e => { e.target.style.borderColor = '#6c5ce7'; e.target.style.boxShadow = '0 0 0 3px rgba(108,92,231,0.1)'; }}
                                onBlur={e => { e.target.style.borderColor = '#e8e4dc'; e.target.style.boxShadow = 'none'; }}
                            />
                        </div>
                    </div>
                )}

                <div style={{ marginBottom: 14 }}>
                    <label style={labelStyle}>Database Name</label>
                    <input value={database} onChange={e => setDatabase(e.target.value)} placeholder="my_database" style={inputStyle}
                        onFocus={e => { e.target.style.borderColor = '#6c5ce7'; e.target.style.boxShadow = '0 0 0 3px rgba(108,92,231,0.1)'; }}
                        onBlur={e => { e.target.style.borderColor = '#e8e4dc'; e.target.style.boxShadow = 'none'; }}
                    />
                </div>

                {postgresOnly && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 24 }}>
                        <div>
                            <label style={labelStyle}>Username</label>
                            <input value={username} onChange={e => setUsername(e.target.value)} placeholder="postgres" style={inputStyle}
                                onFocus={e => { e.target.style.borderColor = '#6c5ce7'; e.target.style.boxShadow = '0 0 0 3px rgba(108,92,231,0.1)'; }}
                                onBlur={e => { e.target.style.borderColor = '#e8e4dc'; e.target.style.boxShadow = 'none'; }}
                            />
                        </div>
                        <div>
                            <label style={labelStyle}>Password</label>
                            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" style={inputStyle}
                                onFocus={e => { e.target.style.borderColor = '#6c5ce7'; e.target.style.boxShadow = '0 0 0 3px rgba(108,92,231,0.1)'; }}
                                onBlur={e => { e.target.style.borderColor = '#e8e4dc'; e.target.style.boxShadow = 'none'; }}
                            />
                        </div>
                    </div>
                )}

                {/* Test Result */}
                {testResult && (
                    <div style={{
                        padding: '14px 18px', borderRadius: 12, marginBottom: 20, fontSize: '0.85rem', fontWeight: 500,
                        background: testResult.success ? '#f0fdf4' : '#fef2f2',
                        border: `1px solid ${testResult.success ? '#bbf7d0' : '#fecaca'}`,
                        color: testResult.success ? '#16a34a' : '#dc2626',
                    }}>
                        {testResult.success ? '✓' : '✕'} {testResult.message}
                    </div>
                )}

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: 12 }}>
                    <button
                        onClick={handleTest}
                        disabled={!database || testing}
                        style={{
                            flex: 1, padding: '13px 20px', borderRadius: 12, border: '1.5px solid #e8e4dc',
                            background: '#fff', color: '#4a4b58', fontFamily: "'DM Sans', sans-serif",
                            fontSize: '0.9rem', fontWeight: 600, cursor: database && !testing ? 'pointer' : 'default',
                            opacity: database && !testing ? 1 : 0.5, transition: 'all 0.2s',
                        }}
                        onMouseEnter={e => { if (database && !testing) e.currentTarget.style.background = '#f7f5f0'; }}
                        onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
                    >
                        {testing ? '⏳ Testing...' : '🔌 Test Connection'}
                    </button>
                    <button
                        onClick={handleConnect}
                        disabled={!database || connecting}
                        style={{
                            flex: 1, padding: '13px 20px', borderRadius: 12, border: 'none',
                            background: database && !connecting ? '#6c5ce7' : '#e8e4dc', color: database && !connecting ? '#fff' : '#9b9da8',
                            fontFamily: "'DM Sans', sans-serif", fontSize: '0.9rem', fontWeight: 600,
                            cursor: database && !connecting ? 'pointer' : 'default', transition: 'all 0.2s',
                            boxShadow: database && !connecting ? '0 2px 12px rgba(108,92,231,0.25)' : 'none',
                        }}
                        onMouseEnter={e => { if (database && !connecting) { e.currentTarget.style.background = '#5a4bd1'; e.currentTarget.style.boxShadow = '0 4px 20px rgba(108,92,231,0.35)'; } }}
                        onMouseLeave={e => { if (database && !connecting) { e.currentTarget.style.background = '#6c5ce7'; e.currentTarget.style.boxShadow = '0 2px 12px rgba(108,92,231,0.25)'; } }}
                    >
                        {connecting ? '⏳ Connecting...' : '→ Connect & Save'}
                    </button>
                </div>
            </div>
        </div>
    );
}
