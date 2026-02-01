'use client';

import { useEffect, useState } from 'react';
import L from 'leaflet';
import { MapContainer, TileLayer, GeoJSON, useMap, useMapEvents, Rectangle } from 'react-leaflet';
import { api, apiClient, type AlertFeatureCollection } from '@/lib/api';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icon in Next.js
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

interface AlertMapProps {
    onAlertSelect?: (alertId: number | null) => void;
    onNewAlert?: (alert: any) => void;
    endpoint?: string;
}

function MapUpdater({ alerts }: { alerts: AlertFeatureCollection | null }) {
    const map = useMap();

    useEffect(() => {
        if (alerts && alerts.features.length > 0) {
            const bounds = L.geoJSON(alerts as any).getBounds();
            if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [50, 50] });
            }
        }
    }, [alerts, map]);

    return null;
}

// Component to display mouse coordinates and grid highlight
function LocationDisplay() {
    const [position, setPosition] = useState<L.LatLng | null>(null);
    useMapEvents({
        mousemove(e) {
            setPosition(e.latlng);
        },
    });

    if (!position) return null;

    return (
        <div className="absolute top-2 right-2 bg-slate-900/90 backdrop-blur-sm text-gray-200 text-xs px-2 py-1 rounded border border-slate-700 z-[1000] font-mono shadow-lg">
            {position.lat.toFixed(4)}, {position.lng.toFixed(4)}
        </div>
    );
}

export default function AlertMap({ onAlertSelect, onNewAlert, endpoint }: AlertMapProps) {
    const [alerts, setAlerts] = useState<AlertFeatureCollection | null>(null);
    const [boundaries, setBoundaries] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [layers, setLayers] = useState<any>(null);
    const [activeLayer, setActiveLayer] = useState<string>('s1_vv_after');
    const [selectedAlertId, setSelectedAlertId] = useState<number | null>(null);


    useEffect(() => {
        loadAlerts();
        loadBoundaries();

        // Poll for new alerts every 12 hours
        const interval = setInterval(() => {
            loadAlerts(true);
        }, 12 * 60 * 60 * 1000);

        return () => clearInterval(interval);
    }, [onNewAlert, endpoint]); // Add endpoint to dependencies

    const loadBoundaries = async () => {
        try {
            const data = await api.getBoundaries('MUNICIPALITY');
            setBoundaries(data);
        } catch (err) {
            console.error('Failed to load boundaries:', err);
        }
    };

    const loadAlerts = async (silent = false) => {
        try {
            if (!silent) setLoading(true);

            let data;
            if (endpoint) {
                // If custom endpoint provided, use it directly via apiClient
                const res = await apiClient.get(endpoint);
                data = res.data;
            } else {
                // Default behavior
                data = await api.getAlerts({ limit: 500 }); // Get last 500 alerts
            }

            // Check for new alerts (only if not demo endpoint essentially, but logic holds)
            if (alerts && data.metadata.total > alerts.metadata.total) {
                // Find new alerts
                const oldIds = new Set(alerts.features.map((f: any) => f.id));
                const newAlerts = data.features.filter((f: any) => !oldIds.has(f.id));

                // Notify for the most recent one if multiple
                if (newAlerts.length > 0 && onNewAlert) {
                    onNewAlert(newAlerts[0].properties);
                }
            }

            setAlerts(data);
        } catch (error) {
            console.error('Failed to load alerts:', error);
        } finally {
            setLoading(false);
        }
    };

    const getAlertStyle = (feature: any) => {
        const isTier2 = feature.properties.risk_tier === 'TIER_2';
        return {
            fillColor: isTier2 ? '#ef4444' : '#f97316',
            weight: 2,
            opacity: 1,
            color: '#ffffff',
            fillOpacity: 0.6,
        };
    };

    const onEachFeature = (feature: any, layer: L.Layer) => {
        const props = feature.properties;

        const popupContent = `
      <div class="text-white">
        <h3 class="font-bold text-lg mb-2">
          Alert #${props.id}
          ${props.risk_tier === 'TIER_2' ? '🔴' : '🟠'}
        </h3>
        <div class="space-y-1 text-sm">
          <p><span class="text-gray-400">Radar Conf:</span> <strong>${(props.confidence_score * 100).toFixed(1)}%</strong></p>
          ${props.optical_score != null ?
                `<p><span class="text-gray-400">Optical Conf:</span> ${(props.optical_score * 100).toFixed(1)}% (Drop: ${props.ndvi_drop?.toFixed(3) || 'N/A'})</p>`
                : '<p><span class="text-gray-400">Optical Conf:</span> <span class="text-gray-500">Pending/Cloudy</span></p>'}
          ${props.combined_score != null ?
                `<p><span class="text-gray-400">Combined:</span> <span class="text-green-400 font-bold">${(props.combined_score * 100).toFixed(1)}%</span></p>`
                : ''}
          <div class="h-px bg-gray-700 my-2"></div>
          <p><span class="text-gray-400">Area:</span> ${props.area_hectares.toFixed(2)} ha</p>
          <p><span class="text-gray-400">VH Drop:</span> ${props.alt_vh_drop_db.toFixed(2)} dB</p>
          <p><span class="text-gray-400">Status:</span> <span class="capitalize">${props.status.toLowerCase()}</span></p>
          ${props.boundary_name ? `<p><span class="text-gray-400">Location:</span> ${props.boundary_name}</p>` : ''}
          <p class="text-xs text-gray-500 mt-2">${new Date(props.detection_date).toLocaleString()}</p>
        </div>
      </div>
    `;

        layer.bindPopup(popupContent, {
            maxWidth: 300,
            className: 'custom-popup',
        });

        layer.on('click', async () => {
            if (onAlertSelect) {
                onAlertSelect(props.id);
            }
            setSelectedAlertId(props.id);

            // Fetch layers for this alert
            try {
                // Use apiClient to fetch directly from layers endpoint
                const res = await apiClient.get(`/layers/${props.id}`);
                setLayers(res.data);
            } catch (e) {
                console.error("Failed to load layers for alert", props.id, e);
                setLayers(null);
            }
        });
    };

    // Uttara Kannada coordinates (Approx Center)
    const center: [number, number] = [14.6, 74.6];

    return (
        <div className="relative w-full h-full">
            <MapContainer
                center={center}
                zoom={9}
                className="absolute inset-0 z-0"
                zoomControl={true}
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {/* Satellite imagery alternative (Esri) */}
                <TileLayer
                    attribution='Tiles &copy; Esri'
                    url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                    opacity={0.7}
                />

                {/* Municipal Boundaries */}
                {boundaries && (
                    <GeoJSON
                        data={boundaries}
                        style={{
                            color: '#fbbf24', // Amber-400
                            weight: 2,
                            opacity: 0.8,
                            fillOpacity: 0.05,
                            fillColor: '#fbbf24',
                            dashArray: '10, 5'
                        }}
                    />
                )}

                {alerts && alerts.features.length > 0 && (
                    <>
                        <GeoJSON
                            data={alerts as any}
                            style={getAlertStyle}
                            onEachFeature={onEachFeature}
                        />
                        <MapUpdater alerts={alerts} />
                    </>
                )}
                {layers && layers[activeLayer] && (
                    <TileLayer
                        url={layers[activeLayer]}
                        opacity={1.0}
                        maxNativeZoom={14} // GEE tiles can get blurry
                        zIndex={50}
                    />
                )}

                <LocationDisplay />
            </MapContainer>

            {/* Layer Control Panel */}
            {layers && (
                <div className="absolute top-4 left-4 bg-slate-900/95 backdrop-blur rounded-lg p-3 border border-slate-700 shadow-xl z-[1000] min-w-[200px]">
                    <h4 className="text-white font-bold text-xs uppercase tracking-wider mb-2">Satellite Layers</h4>
                    <div className="space-y-1">
                        {[
                            { id: 's1_vv_before', label: 'S1 Radar (Before)' },
                            { id: 's1_vv_after', label: 'S1 Radar (After)' },
                            { id: 's2_rgb_before', label: 'S2 Optical (Before)' },
                            { id: 's2_rgb_after', label: 'S2 Optical (After)' },
                            { id: 'ndvi_before', label: 'NDVI (Before)' },
                            { id: 'ndvi_after', label: 'NDVI (After)' }
                        ].map(layer => (
                            <button
                                key={layer.id}
                                onClick={() => setActiveLayer(layer.id)}
                                className={`w-full text-left px-2 py-1.5 text-xs rounded transition-colors ${activeLayer === layer.id
                                    ? 'bg-blue-600 text-white font-semibold'
                                    : 'text-gray-300 hover:bg-slate-800'
                                    }`}
                            >
                                {layer.label}
                                {layers[layer.id] ? '' : ' (N/A)'}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Legend */}
            <div className="absolute bottom-4 left-4 bg-slate-900/90 backdrop-blur-sm rounded-lg p-4 border border-slate-700 shadow-xl z-[1000]">
                <h4 className="text-white font-semibold text-sm mb-3">Alert Risk Tiers</h4>
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="w-6 h-6 rounded bg-red-500"></div>
                        <span className="text-sm text-gray-300">Tier 2 - Protected Areas</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="w-6 h-6 rounded bg-orange-500"></div>
                        <span className="text-sm text-gray-300">Tier 1 - Standard</span>
                    </div>
                </div>

                {alerts && (
                    <div className="mt-3 pt-3 border-t border-slate-700 text-xs text-gray-400">
                        {alerts.features.length} alerts displayed
                        {loading && <span className="ml-2">• Updating...</span>}
                    </div>
                )}
            </div>
        </div>
    );
}
