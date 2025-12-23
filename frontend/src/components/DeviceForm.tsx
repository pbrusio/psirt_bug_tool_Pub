import { useState } from 'react';
import type { DeviceCredentials, PSIRTMetadata } from '../types';

interface DeviceFormProps {
  onVerify: (credentials: DeviceCredentials, metadata: PSIRTMetadata) => void;
  loading?: boolean;
}

export function DeviceForm({ onVerify, loading = false }: DeviceFormProps) {
  const [host, setHost] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [productNames, setProductNames] = useState('');
  const [bugId, setBugId] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const credentials: DeviceCredentials = {
      host: host.trim(),
      username: username.trim(),
      password,
      device_type: 'cisco_ios',
    };

    const metadata: PSIRTMetadata = {
      product_names: productNames.trim()
        ? productNames.split('\n').map((p) => p.trim()).filter(Boolean)
        : [],
      bug_id: bugId.trim() || undefined,
    };

    onVerify(credentials, metadata);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="alert alert-info">
        <p className="text-sm">
          This will connect to your device via SSH and verify the vulnerability status.
          Credentials are not stored.
        </p>
      </div>

      <div>
        <label htmlFor="host" className="label">
          Device IP/Hostname *
        </label>
        <input
          id="host"
          type="text"
          value={host}
          onChange={(e) => setHost(e.target.value)}
          placeholder="192.168.0.33"
          className="input"
          disabled={loading}
          required
        />
      </div>

      <div>
        <label htmlFor="username" className="label">
          Username *
        </label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="admin"
          className="input"
          disabled={loading}
          required
        />
      </div>

      <div>
        <label htmlFor="password" className="label">
          Password *
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          className="input"
          disabled={loading}
          required
        />
      </div>

      {/* Advanced Options (Collapsible) */}
      <div>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-sm font-medium text-blue-600 hover:text-blue-700 flex items-center gap-1"
        >
          <span>{showAdvanced ? '▼' : '▶'}</span>
          Advanced Options (Optional)
        </button>

        {showAdvanced && (
          <div className="mt-3 space-y-4 p-4 bg-gray-50 rounded-md">
            <div>
              <label htmlFor="bugId" className="label">
                Bug/Advisory ID
              </label>
              <input
                id="bugId"
                type="text"
                value={bugId}
                onChange={(e) => setBugId(e.target.value)}
                placeholder="cisco-sa-iox-dos-95Fqnf7b"
                className="input"
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="productNames" className="label">
                Affected Product Names (one per line)
              </label>
              <textarea
                id="productNames"
                value={productNames}
                onChange={(e) => setProductNames(e.target.value)}
                placeholder="Cisco IOS XE Software, Version 17.3.1&#10;Cisco IOS XE Software, Version 17.3.2"
                rows={3}
                className="input"
                disabled={loading}
              />
              <p className="text-xs text-gray-500 mt-1">
                Used for version matching. Leave empty to skip version check.
              </p>
            </div>
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={loading || !host.trim() || !username.trim() || !password}
        className={`btn w-full ${
          loading || !host.trim() || !username.trim() || !password
            ? 'btn-disabled'
            : 'btn-success'
        }`}
      >
        {loading ? (
          <span className="flex items-center justify-center">
            <span className="spinner h-5 w-5 mr-2"></span>
            Connecting to Device...
          </span>
        ) : (
          'Connect & Verify Device'
        )}
      </button>
    </form>
  );
}
