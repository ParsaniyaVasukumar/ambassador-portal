(async function () {
  const mapEl = document.getElementById('map');
  if (!mapEl) return;

  const skeleton = document.getElementById('mapSkeleton');
  const topList = document.getElementById('topStatesList');

  function removeSkeleton() {
    skeleton?.remove();
  }

  function showMapError(message) {
    removeSkeleton();
    mapEl.innerHTML = `<div class="w-full h-full flex items-center justify-center text-sm text-ink-500 text-center px-6">${message}</div>`;
  }

  let statesRes, geoRes;
  try {
    [statesRes, geoRes] = await Promise.all([
      fetch('/api/states').then(r => r.json()),
      fetch(window.GEOJSON_URL).then(r => r.json()).catch(() => null),
    ]);
  } catch (e) {
    showMapError('Could not load ambassador data right now. Try refreshing the page.');
    if (topList) topList.innerHTML = '<li class="text-ink-500">Unavailable</li>';
    return;
  }

  const map = L.map('map', { scrollWheelZoom: false }).setView([22.5, 80], 4.4);
  L.control.zoom({ position: 'topright' }).addTo(map);

  // Aggregate by lowercase geo_state so slight spelling/casing differences in the
  // sheet don't silently overwrite each other — every matching row is summed.
  const countByGeoName = {};
  let maxCount = 1;
  statesRes.forEach(s => {
    const key = (s.geo_state || '').trim().toLowerCase();
    if (!key) return;
    countByGeoName[key] = (countByGeoName[key] || 0) + s.count;
  });
  Object.values(countByGeoName).forEach(c => { if (c > maxCount) maxCount = c; });

  function countFor(name) {
    return countByGeoName[(name || '').trim().toLowerCase()] || 0;
  }

  // The public India-states GeoJSON this app uses stores the state name under
  // the property key "ST_NM" (uppercase). We also check a couple of common
  // fallbacks in case a different geojson source is swapped in later.
  function nameFor(feature) {
    const p = feature.properties || {};
    return p.ST_NM || p.st_nm || p.NAME_1 || p.name || 'Unknown';
  }

  function colorFor(count) {
    if (!count) return '#f3f4f6';
    const t = count / maxCount;
    if (t > 0.75) return '#c22a1f';
    if (t > 0.5) return '#e8382b';
    if (t > 0.25) return '#ff5a45';
    return '#ffb8b0';
  }

  if (topList) {
    topList.innerHTML = '';
    if (statesRes.length === 0) {
      topList.innerHTML = '<li class="text-ink-500">No data yet</li>';
    } else {
      statesRes.slice(0, 8).forEach(s => {
        const li = document.createElement('li');
        li.className = 'flex items-center justify-between';
        li.innerHTML = `<a href="/roster?state=${encodeURIComponent(s.state_display)}" class="text-ink-700 hover:text-brand-600 hover:underline">${s.state_display}</a><span class="font-semibold text-ink-900">${s.count}</span>`;
        topList.appendChild(li);
      });
    }
  }

  if (geoRes) {
    const layer = L.geoJSON(geoRes, {
      style: feature => ({
        fillColor: colorFor(countFor(nameFor(feature))),
        weight: 1,
        color: '#ffffff',
        fillOpacity: 0.9,
      }),
      onEachFeature: (feature, lyr) => {
        const name = nameFor(feature);
        const count = countFor(name);
        lyr.bindTooltip(`${name}: ${count} ambassador${count === 1 ? '' : 's'}`, { sticky: true });
        lyr.on('click', () => {
          document.getElementById('stateSelectedLabel').textContent = `${name} — ${count} ambassador${count === 1 ? '' : 's'}`;
          window.location.href = `/roster?state=${encodeURIComponent(name)}`;
        });
        lyr.on('mouseover', () => lyr.setStyle({ weight: 2, color: '#e8382b' }));
        lyr.on('mouseout', () => lyr.setStyle({ weight: 1, color: '#ffffff' }));
      },
    }).addTo(map);
    map.fitBounds(layer.getBounds());
    removeSkeleton();
  } else {
    showMapError('Map data unavailable right now. The ambassador list and analytics are unaffected.');
  }
})();