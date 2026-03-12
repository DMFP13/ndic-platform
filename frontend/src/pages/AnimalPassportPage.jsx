import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import {
  ArrowLeft, Edit2, Save, X, Plus, Trash2, Camera, Upload,
  Thermometer, Weight, Droplets, Heart, Activity, Wheat,
  CheckCircle, AlertTriangle, AlertCircle, FileText, Syringe,
  Stethoscope, Scale, Baby, StickyNote, MoreHorizontal, Search,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext.jsx';
import {
  getAnimalPassport, createVetRecord, updateVetRecord, deleteVetRecord,
  uploadAnimalPhoto, deleteAnimalPhoto, identifyFromPhoto,
} from '../api/endpoints.js';

// ── Constants ────────────────────────────────────────────────────────────────

const WRITE_ROLES = ['farm_manager', 'farm_admin', 'farm_vet'];

const VET_RECORD_TYPES = [
  { value: 'vaccination',      label: 'Vaccination',       icon: Syringe },
  { value: 'treatment',        label: 'Treatment',         icon: Stethoscope },
  { value: 'disease',          label: 'Disease',           icon: AlertCircle },
  { value: 'weight_check',     label: 'Weight Check',      icon: Scale },
  { value: 'pregnancy_check',  label: 'Pregnancy Check',   icon: Heart },
  { value: 'calving',          label: 'Calving',           icon: Baby },
  { value: 'note',             label: 'Note',              icon: StickyNote },
  { value: 'other',            label: 'Other',             icon: MoreHorizontal },
];

const TYPE_META = Object.fromEntries(VET_RECORD_TYPES.map((t) => [t.value, t]));

const STATUS_STYLE = {
  healthy:  { bg: 'bg-green-100',  text: 'text-green-800',  label: 'Healthy' },
  at_risk:  { bg: 'bg-amber-100',  text: 'text-amber-800',  label: 'At Risk' },
  critical: { bg: 'bg-red-100',    text: 'text-red-800',    label: 'Critical' },
};

// ── Small shared components ──────────────────────────────────────────────────

function MockBanner({ onDismiss }) {
  return (
    <div className="flex items-center gap-2 bg-amber-50 border border-amber-300 rounded-lg px-4 py-2.5 text-xs text-amber-800 font-medium">
      <AlertTriangle size={14} className="flex-shrink-0" />
      <span className="flex-1">
        <strong>MOCK DATA</strong> — sensor readings and records are simulated.
        Connect real sensors and the live backend to replace.
      </span>
      <button onClick={onDismiss} className="text-amber-600 hover:text-amber-800 flex-shrink-0">
        <X size={14} />
      </button>
    </div>
  );
}

function StatusBadge({ status }) {
  const s = STATUS_STYLE[status] || { bg: 'bg-gray-100', text: 'text-gray-700', label: status };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

function SensorCard({ icon: Icon, label, value, unit, alert, isMock }) {
  return (
    <div className={`bg-white rounded-lg border p-3 flex flex-col gap-1 ${alert ? 'border-red-300' : 'border-gray-200'}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">{label}</span>
        <Icon size={14} className={alert ? 'text-red-500' : 'text-gray-400'} />
      </div>
      <div className="flex items-end gap-1">
        <span className={`text-xl font-bold tabular-nums ${alert ? 'text-red-600' : 'text-gray-900'}`}>
          {value ?? '—'}
        </span>
        <span className="text-xs text-gray-400 mb-0.5">{unit}</span>
      </div>
      {isMock && <span className="text-[10px] text-amber-600 font-medium">MOCK</span>}
    </div>
  );
}

function ChartCard({ title, data, dataKey, color, unit, isMock }) {
  if (!data || data.length === 0) return null;
  const chartData = data.map((r, i) => ({
    i,
    v: r[dataKey],
    label: new Date(r.timestamp).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }),
  }));
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        {isMock && <span className="text-[10px] text-amber-600 font-medium bg-amber-50 px-1.5 py-0.5 rounded">MOCK</span>}
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="i"
            tick={false}
            tickLine={false}
          />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
          <Tooltip
            formatter={(v) => [`${v} ${unit}`, title]}
            labelFormatter={(idx) => chartData[idx]?.label || ''}
            contentStyle={{ fontSize: 11, padding: '4px 8px' }}
          />
          <Line type="monotone" dataKey="v" stroke={color} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Vet Record type icon ──────────────────────────────────────────────────────

function VetTypeIcon({ type, size = 14 }) {
  const meta = TYPE_META[type] || TYPE_META.other;
  const Icon = meta.icon;
  const colors = {
    vaccination: 'text-blue-600 bg-blue-50',
    treatment:   'text-purple-600 bg-purple-50',
    disease:     'text-red-600 bg-red-50',
    weight_check:'text-gray-600 bg-gray-100',
    pregnancy_check: 'text-pink-600 bg-pink-50',
    calving:     'text-green-600 bg-green-50',
    note:        'text-amber-600 bg-amber-50',
    other:       'text-gray-600 bg-gray-100',
  };
  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full flex-shrink-0 ${colors[type] || colors.other}`}>
      <Icon size={size} />
    </span>
  );
}

// ── Vet Record Form ───────────────────────────────────────────────────────────

const EMPTY_FORM = {
  record_type: 'vaccination',
  record_date: new Date().toISOString().slice(0, 10),
  title: '',
  description: '',
  drug_name: '', dosage: '', route: '', duration_days: '', withdrawal_period_days: '',
  vaccine_name: '', vaccine_batch: '', next_due_date: '',
  disease_name: '', outcome: '',
  vet_name: '', vet_contact: '', notes: '',
};

function VetRecordForm({ initial, onSave, onCancel, saving }) {
  const [form, setForm] = useState(initial || EMPTY_FORM);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const type = form.record_type;

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Type *</label>
          <select
            value={type}
            onChange={(e) => set('record_type', e.target.value)}
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white"
          >
            {VET_RECORD_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Date *</label>
          <input
            type="date"
            value={form.record_date}
            onChange={(e) => set('record_date', e.target.value)}
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Title *</label>
        <input
          type="text"
          value={form.title}
          onChange={(e) => set('title', e.target.value)}
          placeholder="e.g. FMD Vaccination — annual"
          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
        <textarea
          value={form.description}
          onChange={(e) => set('description', e.target.value)}
          rows={2}
          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white resize-none"
        />
      </div>

      {/* Vaccination fields */}
      {type === 'vaccination' && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Vaccine Name</label>
            <input type="text" value={form.vaccine_name} onChange={(e) => set('vaccine_name', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Batch Number</label>
            <input type="text" value={form.vaccine_batch} onChange={(e) => set('vaccine_batch', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
          </div>
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-700 mb-1">Next Due Date</label>
            <input type="date" value={form.next_due_date} onChange={(e) => set('next_due_date', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
          </div>
        </div>
      )}

      {/* Treatment fields */}
      {type === 'treatment' && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Drug / Product</label>
            <input type="text" value={form.drug_name} onChange={(e) => set('drug_name', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Dosage</label>
            <input type="text" value={form.dosage} onChange={(e) => set('dosage', e.target.value)}
              placeholder="e.g. 20 mg/kg"
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Route</label>
            <select value={form.route} onChange={(e) => set('route', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white">
              <option value="">Select…</option>
              {['IM', 'IV', 'SC', 'Oral', 'Topical', 'Intranasal'].map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Duration (days)</label>
            <input type="number" min="1" value={form.duration_days} onChange={(e) => set('duration_days', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
          </div>
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-700 mb-1">Withdrawal Period (days)</label>
            <input type="number" min="0" value={form.withdrawal_period_days} onChange={(e) => set('withdrawal_period_days', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
          </div>
        </div>
      )}

      {/* Disease fields */}
      {type === 'disease' && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Disease Name</label>
            <input type="text" value={form.disease_name} onChange={(e) => set('disease_name', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Outcome</label>
            <select value={form.outcome} onChange={(e) => set('outcome', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white">
              <option value="">Select…</option>
              {['Ongoing', 'Recovered', 'Died', 'Culled', 'Referred'].map((o) => (
                <option key={o} value={o.toLowerCase()}>{o}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Vet / Recorded by</label>
          <input type="text" value={form.vet_name} onChange={(e) => set('vet_name', e.target.value)}
            placeholder="Dr. Name or Farm Manager"
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Contact</label>
          <input type="text" value={form.vet_contact} onChange={(e) => set('vet_contact', e.target.value)}
            placeholder="email or phone"
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white" />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
        <textarea value={form.notes} onChange={(e) => set('notes', e.target.value)}
          rows={2}
          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white resize-none" />
      </div>

      <div className="flex gap-2 pt-1">
        <button
          onClick={() => onSave(form)}
          disabled={saving || !form.title.trim()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Save size={13} /> {saving ? 'Saving…' : 'Save Record'}
        </button>
        <button onClick={onCancel}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-300 text-gray-700 text-xs font-semibold rounded-lg hover:bg-gray-50">
          <X size={13} /> Cancel
        </button>
      </div>
    </div>
  );
}

// ── Photo Gallery ─────────────────────────────────────────────────────────────

function PhotoGallery({ photos, canEdit, animalId, farmId, onPhotosChange }) {
  const [mlResult, setMlResult] = useState(null);
  const [identifying, setIdentifying] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [lightbox, setLightbox] = useState(null);
  const fileRef = useRef(null);
  const cameraRef = useRef(null);

  async function handleUpload(file) {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await uploadAnimalPhoto(farmId, animalId, fd);
      onPhotosChange([...photos, res.data]);
    } catch {
      // backend not available — show mock preview
      const url = URL.createObjectURL(file);
      onPhotosChange([...photos, { id: `local-${Date.now()}`, url, filename: file.name, is_primary: photos.length === 0, is_local_preview: true }]);
    } finally {
      setUploading(false);
    }
  }

  async function handleIdentify(file) {
    if (!file) return;
    setIdentifying(true);
    setMlResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await identifyFromPhoto(fd);
      setMlResult(res.data);
    } catch {
      setMlResult({
        is_mock: true,
        matched_tag: `NG-${Math.floor(Math.random() * 900) + 100}`,
        confidence: +(Math.random() * 0.36 + 0.61).toFixed(3),
        confidence_label: 'Medium',
        message: 'MOCK RESULT — backend unavailable.',
      });
    } finally {
      setIdentifying(false);
    }
  }

  async function handleDelete(photoId) {
    try { await deleteAnimalPhoto(farmId, animalId, photoId); } catch { /* ignore */ }
    onPhotosChange(photos.filter((p) => p.id !== photoId));
  }

  const confColor = mlResult
    ? mlResult.confidence > 0.85 ? 'text-green-700 bg-green-50 border-green-200'
    : mlResult.confidence > 0.70 ? 'text-amber-700 bg-amber-50 border-amber-200'
    : 'text-red-700 bg-red-50 border-red-200'
    : '';

  return (
    <div>
      {/* Upload bar */}
      {canEdit && (
        <div className="flex gap-2 mb-3 flex-wrap">
          <button
            onClick={() => cameraRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <Camera size={13} /> {uploading ? 'Uploading…' : 'Take Photo'}
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-300 text-gray-700 text-xs font-semibold rounded-lg hover:bg-gray-50"
          >
            <Upload size={13} /> Upload
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={identifying}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 text-white text-xs font-semibold rounded-lg hover:bg-purple-700 disabled:opacity-50"
          >
            <Search size={13} /> {identifying ? 'Identifying…' : 'ID from Photo (ML)'}
          </button>

          {/* Hidden inputs */}
          <input
            ref={cameraRef} type="file" accept="image/*" capture="environment" className="hidden"
            onChange={(e) => handleUpload(e.target.files?.[0])}
          />
          <input
            ref={fileRef} type="file" accept="image/*" className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) { handleUpload(f); handleIdentify(f); }
            }}
          />
        </div>
      )}

      {/* ML result */}
      {mlResult && (
        <div className={`mb-3 flex items-start gap-3 p-3 rounded-lg border text-xs ${confColor}`}>
          <Search size={14} className="flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">
              ID Result: <span className="font-bold">{mlResult.matched_tag}</span>
              {' '}— {(mlResult.confidence * 100).toFixed(1)}% confidence
              {' '}({mlResult.confidence_label})
            </p>
            <p className="mt-0.5 opacity-75">{mlResult.message}</p>
            {mlResult.is_mock && <span className="font-bold">MOCK</span>}
          </div>
          <button onClick={() => setMlResult(null)}><X size={12} /></button>
        </div>
      )}

      {/* Photo grid */}
      {photos.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-6">No photos yet. {canEdit ? 'Take or upload the first one.' : ''}</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {photos.map((photo) => (
            <div key={photo.id} className="relative group aspect-square rounded-lg overflow-hidden bg-gray-100 border border-gray-200 cursor-pointer"
              onClick={() => setLightbox(photo)}>
              <img
                src={photo.url}
                alt={photo.filename}
                className="w-full h-full object-cover"
                onError={(e) => { e.target.style.display = 'none'; }}
              />
              {photo.is_primary && (
                <span className="absolute top-1 left-1 text-[10px] bg-blue-600 text-white px-1 py-0.5 rounded font-semibold">Primary</span>
              )}
              {canEdit && (
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(photo.id); }}
                  className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 bg-red-600 text-white rounded-full p-0.5 transition-opacity"
                >
                  <X size={10} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {lightbox && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setLightbox(null)}>
          <div className="max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
            <img src={lightbox.url} alt={lightbox.filename} className="w-full rounded-lg" />
            <p className="text-white text-xs mt-2 text-center">{lightbox.filename}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AnimalPassportPage() {
  const { animalId, farmId: paramFarmId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const farmId = paramFarmId || user?.org_id || 'demo-org';
  const canEdit = WRITE_ROLES.includes(user?.role);

  const [passport, setPassport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [showMockBanner, setShowMockBanner] = useState(true);

  // Vet records state
  const [vetRecords, setVetRecords] = useState([]);
  const [vetFilter, setVetFilter] = useState('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingRecord, setEditingRecord] = useState(null);
  const [savingVet, setSavingVet] = useState(false);

  // Photos
  const [photos, setPhotos] = useState([]);

  // Section expansion (mobile UX)
  const [expanded, setExpanded] = useState({ sensors: true, charts: false, vet: true, photos: true });
  const toggle = (key) => setExpanded((s) => ({ ...s, [key]: !s[key] }));

  const loadPassport = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await getAnimalPassport(farmId, animalId);
      const data = res.data;
      setPassport(data);
      setVetRecords(data.vet_records || []);
      setPhotos(data.photos || []);
      if (data.is_mock) setShowMockBanner(true);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [farmId, animalId]);

  useEffect(() => { loadPassport(); }, [loadPassport]);

  async function handleAddVetRecord(form) {
    setSavingVet(true);
    try {
      const res = await createVetRecord(farmId, animalId, form);
      const newRecord = { ...res.data, is_mock: true };
      setVetRecords((prev) => [newRecord, ...prev]);
      setShowAddForm(false);
    } catch {
      // optimistic mock insert
      const mockRecord = {
        id: `local-${Date.now()}`,
        ...form,
        is_mock: true,
        created_at: new Date().toISOString(),
      };
      setVetRecords((prev) => [mockRecord, ...prev]);
      setShowAddForm(false);
    } finally {
      setSavingVet(false);
    }
  }

  async function handleUpdateVetRecord(form) {
    setSavingVet(true);
    try {
      await updateVetRecord(farmId, animalId, editingRecord.id, form);
      setVetRecords((prev) => prev.map((r) => r.id === editingRecord.id ? { ...r, ...form } : r));
    } catch {
      setVetRecords((prev) => prev.map((r) => r.id === editingRecord.id ? { ...r, ...form } : r));
    } finally {
      setSavingVet(false);
      setEditingRecord(null);
    }
  }

  async function handleDeleteVetRecord(id) {
    try { await deleteVetRecord(farmId, animalId, id); } catch { /* ignore */ }
    setVetRecords((prev) => prev.filter((r) => r.id !== id));
  }

  // ── Loading / Error states ────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading passport…</p>
        </div>
      </div>
    );
  }

  if (error || !passport) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="text-center">
          <AlertTriangle size={32} className="text-amber-500 mx-auto mb-2" />
          <p className="text-sm text-gray-700 font-medium">Could not load passport</p>
          <button onClick={loadPassport} className="mt-3 text-xs text-blue-600 underline">Retry</button>
        </div>
      </div>
    );
  }

  const { identity, current_sensors: sensors, sensor_series } = passport;

  const filteredVetRecords = vetFilter === 'all'
    ? vetRecords
    : vetRecords.filter((r) => r.record_type === vetFilter);

  const sensorTemp = sensors?.temperature_celsius;
  const tempAlert = sensorTemp != null && (sensorTemp > 39.5 || sensorTemp < 37.5);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sticky header */}
      <div className="sticky top-0 z-20 bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-gray-500 hover:text-gray-700">
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-base font-bold text-gray-900 truncate">
            {identity.tag}
          </h1>
          <p className="text-xs text-gray-500 truncate">{identity.breed}</p>
        </div>
        <StatusBadge status={identity.status} />
      </div>

      <div className="max-w-2xl mx-auto px-4 py-4 space-y-4">

        {/* Mock banner */}
        {passport.is_mock && showMockBanner && (
          <MockBanner onDismiss={() => setShowMockBanner(false)} />
        )}

        {/* ── Hero card ── */}
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="flex gap-4 p-4">
            {/* Primary photo placeholder */}
            <div className="w-24 h-24 rounded-lg bg-gray-100 border border-gray-200 flex-shrink-0 overflow-hidden flex items-center justify-center">
              {photos.find((p) => p.is_primary) ? (
                <img
                  src={photos.find((p) => p.is_primary).url}
                  alt="primary"
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-3xl">🐄</span>
              )}
            </div>

            {/* Identity grid */}
            <div className="flex-1 min-w-0 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
              <InfoRow label="Tag" value={identity.tag} />
              <InfoRow label="Microchip" value={identity.microchip} />
              <InfoRow label="Breed" value={identity.breed} />
              <InfoRow label="Sex" value={identity.sex} />
              <InfoRow label="Date of Birth" value={identity.date_of_birth} />
              <InfoRow label="Age" value={`${identity.age_months} months`} />
              <InfoRow label="Colour" value={identity.colour_markings} />
              <InfoRow label="Status" value={<StatusBadge status={identity.status} />} />
              <InfoRow label="Dam" value={identity.dam_tag} />
              <InfoRow label="Sire" value={identity.sire_tag} />
            </div>
          </div>
        </div>

        {/* ── Live Sensors ── */}
        <Section title="Live Sensor Readings" expanded={expanded.sensors} onToggle={() => toggle('sensors')}>
          {sensors && (
            <>
              <p className="text-[11px] text-amber-600 mb-2">
                Last reading: {sensors.as_of ? new Date(sensors.as_of).toLocaleString() : 'Unknown'}
                {sensors.is_mock && ' — MOCK DATA'}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <SensorCard icon={Thermometer} label="Temperature" value={sensors.temperature_celsius} unit="°C" alert={tempAlert} isMock={sensors.is_mock} />
                <SensorCard icon={Weight} label="Weight" value={sensors.weight_kg} unit="kg" isMock={sensors.is_mock} />
                <SensorCard icon={Droplets} label="Milk Yield" value={sensors.milk_yield_liters} unit="L" isMock={sensors.is_mock} />
                <SensorCard icon={Heart} label="Heart Rate" value={sensors.heart_rate_bpm} unit="bpm" isMock={sensors.is_mock} />
                <SensorCard icon={Activity} label="Activity" value={sensors.activity_index} unit="/100" isMock={sensors.is_mock} />
                <SensorCard icon={Wheat} label="Feed Intake" value={sensors.feed_intake_kg} unit="kg" isMock={sensors.is_mock} />
              </div>
              {tempAlert && (
                <div className="mt-2 flex items-center gap-2 p-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                  <AlertTriangle size={13} /> Temperature outside normal range (37.5–39.5°C)
                </div>
              )}
            </>
          )}
        </Section>

        {/* ── Sensor Charts ── */}
        <Section title="30-Day Trends" expanded={expanded.charts} onToggle={() => toggle('charts')}>
          <div className="space-y-3">
            <ChartCard
              title="Milk Yield (L/day)"
              data={sensor_series}
              dataKey="milk_yield_liters"
              color="#2563EB"
              unit="L"
              isMock={passport.is_mock}
            />
            <ChartCard
              title="Weight (kg)"
              data={sensor_series}
              dataKey="weight_kg"
              color="#16A34A"
              unit="kg"
              isMock={passport.is_mock}
            />
            <ChartCard
              title="Temperature (°C)"
              data={sensor_series}
              dataKey="temperature_celsius"
              color="#DC2626"
              unit="°C"
              isMock={passport.is_mock}
            />
          </div>
        </Section>

        {/* ── Vet Records ── */}
        <Section
          title={`Vet Records (${vetRecords.length})`}
          expanded={expanded.vet}
          onToggle={() => toggle('vet')}
          action={
            canEdit && !showAddForm ? (
              <button
                onClick={() => { setShowAddForm(true); setEditingRecord(null); }}
                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-semibold"
              >
                <Plus size={13} /> Add
              </button>
            ) : null
          }
        >
          {/* Filter tabs */}
          <div className="flex gap-1.5 flex-wrap mb-3">
            {['all', ...VET_RECORD_TYPES.map((t) => t.value)].map((f) => (
              <button
                key={f}
                onClick={() => setVetFilter(f)}
                className={`px-2 py-0.5 rounded-full text-xs border font-medium transition-colors ${
                  vetFilter === f
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {f === 'all' ? 'All' : TYPE_META[f]?.label || f}
              </button>
            ))}
          </div>

          {/* Add form */}
          {showAddForm && (
            <div className="mb-3">
              <VetRecordForm
                onSave={handleAddVetRecord}
                onCancel={() => setShowAddForm(false)}
                saving={savingVet}
              />
            </div>
          )}

          {/* Record list */}
          {filteredVetRecords.length === 0 ? (
            <p className="text-sm text-gray-400 py-4 text-center">No records found.</p>
          ) : (
            <div className="space-y-2">
              {filteredVetRecords.map((rec) => (
                <div key={rec.id}>
                  {editingRecord?.id === rec.id ? (
                    <VetRecordForm
                      initial={editingRecord}
                      onSave={handleUpdateVetRecord}
                      onCancel={() => setEditingRecord(null)}
                      saving={savingVet}
                    />
                  ) : (
                    <VetRecordItem
                      record={rec}
                      canEdit={canEdit}
                      onEdit={() => setEditingRecord(rec)}
                      onDelete={() => handleDeleteVetRecord(rec.id)}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* ── Photos ── */}
        <Section title={`Photos (${photos.length})`} expanded={expanded.photos} onToggle={() => toggle('photos')}>
          <PhotoGallery
            photos={photos}
            canEdit={canEdit}
            animalId={animalId}
            farmId={farmId}
            onPhotosChange={setPhotos}
          />
        </Section>

        <div className="h-8" />
      </div>
    </div>
  );
}

// ── Micro-components ──────────────────────────────────────────────────────────

function InfoRow({ label, value }) {
  return (
    <div className="flex flex-col">
      <span className="text-gray-400">{label}</span>
      <span className="font-medium text-gray-800 truncate">{value ?? '—'}</span>
    </div>
  );
}

function Section({ title, expanded, onToggle, children, action }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 text-left"
        onClick={onToggle}
      >
        <span className="text-sm font-semibold text-gray-900">{title}</span>
        <div className="flex items-center gap-2">
          {action && <span onClick={(e) => e.stopPropagation()}>{action}</span>}
          <span className="text-gray-400 text-xs">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>
      {expanded && <div className="px-4 pb-4 pt-1">{children}</div>}
    </div>
  );
}

function VetRecordItem({ record, canEdit, onEdit, onDelete }) {
  const [confirm, setConfirm] = useState(false);
  const meta = TYPE_META[record.record_type] || TYPE_META.other;

  return (
    <div className="flex gap-3 p-3 rounded-lg border border-gray-100 hover:border-gray-200 bg-gray-50/50">
      <VetTypeIcon type={record.record_type} />
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs font-semibold text-gray-800 leading-tight">{record.title}</p>
            <p className="text-[11px] text-gray-500 mt-0.5">{record.record_date} · {meta.label}</p>
          </div>
          {canEdit && !confirm && (
            <div className="flex gap-1 flex-shrink-0">
              <button onClick={onEdit} className="p-1 text-gray-400 hover:text-blue-600 rounded">
                <Edit2 size={12} />
              </button>
              <button onClick={() => setConfirm(true)} className="p-1 text-gray-400 hover:text-red-600 rounded">
                <Trash2 size={12} />
              </button>
            </div>
          )}
          {confirm && (
            <div className="flex gap-1 flex-shrink-0">
              <button onClick={onDelete} className="text-[11px] px-2 py-0.5 bg-red-600 text-white rounded font-semibold">Delete</button>
              <button onClick={() => setConfirm(false)} className="text-[11px] px-2 py-0.5 bg-white border border-gray-300 rounded">Cancel</button>
            </div>
          )}
        </div>

        {record.description && <p className="text-xs text-gray-600 mt-1">{record.description}</p>}

        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-[11px] text-gray-500">
          {record.vaccine_name && <span>💉 {record.vaccine_name}{record.vaccine_batch ? ` (${record.vaccine_batch})` : ''}</span>}
          {record.next_due_date && <span className="text-blue-600">Next due: {record.next_due_date}</span>}
          {record.drug_name && <span>💊 {record.drug_name}{record.dosage ? ` · ${record.dosage}` : ''}{record.route ? ` · ${record.route}` : ''}</span>}
          {record.withdrawal_period_days != null && <span className="text-amber-600">Withdrawal: {record.withdrawal_period_days}d</span>}
          {record.disease_name && <span>🦠 {record.disease_name}{record.outcome ? ` — ${record.outcome}` : ''}</span>}
          {record.vet_name && <span>👤 {record.vet_name}</span>}
        </div>

        {record.notes && <p className="text-[11px] text-gray-500 italic mt-1">{record.notes}</p>}

        {record.is_mock && <span className="text-[10px] text-amber-600 font-medium">MOCK</span>}
      </div>
    </div>
  );
}
