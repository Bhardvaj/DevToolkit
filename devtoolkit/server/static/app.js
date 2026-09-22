let activeTab = 'env';
    let allReports = [];
    let allPorts = [];
    let currentCategory = 'all';
    try {
      const savedCat = localStorage.getItem('devtoolkit_last_category');
      if (savedCat) currentCategory = savedCat;
    } catch (e) {}
    let currentStatusFilter = null; // null | 'all' | 'installed' | 'healthy' | 'warning' | 'error' | 'not_found'
    let currentLayout = 'grid';
    let currentSort = 'severity';
    let currentPortView = 'flat'; // 'flat' | 'grouped'
    let currentConfig = { search_paths: [] };
    let pendingKill = null;
    let lastScanTime = Date.now();
    let activeDrawerToolId = null;
    let currentProjectActions = [];

    function showToast(msg, isError = false) {
      const toast = document.getElementById('toast');
      const icon = document.getElementById('toast-icon');
      document.getElementById('toast-msg').innerText = msg;
      if (isError) {
        toast.className = 'fixed bottom-10 right-6 px-3.5 py-2 rounded bg-[#0E1015] border border-[#EF4444] text-[#EF4444] text-xs font-mono shadow-2xl transform translate-y-0 opacity-100 transition duration-200 flex items-center gap-2 z-50';
        icon.className = 'fa-solid fa-triangle-exclamation text-xs';
      } else {
        toast.className = 'fixed bottom-10 right-6 px-3.5 py-2 rounded bg-[#0E1015] border border-[#10B981] text-[#10B981] text-xs font-mono shadow-2xl transform translate-y-0 opacity-100 transition duration-200 flex items-center gap-2 z-50';
        icon.className = 'fa-solid fa-check text-xs';
      }
      setTimeout(() => {
        toast.className = 'fixed bottom-10 right-6 px-3.5 py-2 rounded bg-[#0E1015] border border-[#10B981] text-[#10B981] text-xs font-mono shadow-2xl transform translate-y-20 opacity-0 transition duration-200 flex items-center gap-2 z-50';
      }, 2800);
    }

    function copyToClipboard(text, label) {
      if (!text) return;
      navigator.clipboard.writeText(text);
      showToast('Copied ' + (label || 'content') + ' to clipboard!');
    }

    function escapeHtml(str) {
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    async function openFolder(path) {
      if (!path) return;
      try {
        const res = await fetch('/api/action/open-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path })
        });
        const data = await res.json();
        if (res.ok) {
          showToast('Opened in File Explorer');
        } else {
          showToast(data.detail || 'Failed to open folder', true);
        }
      } catch (err) {
        showToast('Error opening folder', true);
      }
    }

    async function applyFix(command) {
      try {
        const res = await fetch('/api/action/apply-fix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command })
        });
        const data = await res.json();
        if (data.status === 'ok') {
          showToast(data.message);
          setTimeout(() => fetchAudit(), 1000);
        } else {
          navigator.clipboard.writeText(command);
          showToast(data.message || 'Copied command to clipboard');
        }
      } catch (e) {
        navigator.clipboard.writeText(command);
        showToast('Copied command to clipboard');
      }
    }

    // Tab Switching
    function switchTab(tab) {
      activeTab = tab;
      const tabs = ['env', 'search', 'ports', 'project', 'settings'];
      tabs.forEach(t => {
        const btn = document.getElementById(`nav-btn-${t}`);
        const view = document.getElementById(`view-${t}`);
        if (btn && view) {
          if (t === tab) {
            btn.className = 'w-full flex items-center justify-between px-2.5 py-2 rounded text-xs font-medium transition nav-active';
            view.classList.remove('hidden');
          } else {
            btn.className = 'w-full flex items-center justify-between px-2.5 py-2 rounded text-xs font-medium transition nav-inactive';
            view.classList.add('hidden');
          }
        }
      });

      // Show/hide top search bar & rescan button based on active tab (only visible on Environment tab)
      const searchWrapper = document.getElementById('top-search-wrapper');
      const rescanBtn = document.getElementById('rescan-btn');
      const exportWrapper = document.getElementById('export-dropdown-wrapper');
      if (tab === 'env') {
        if (searchWrapper) searchWrapper.classList.remove('hidden');
        if (rescanBtn) rescanBtn.classList.remove('hidden');
        if (exportWrapper) exportWrapper.classList.remove('hidden');
      } else {
        if (searchWrapper) searchWrapper.classList.add('hidden');
        if (rescanBtn) rescanBtn.classList.add('hidden');
        if (exportWrapper) exportWrapper.classList.add('hidden');
      }

      // Update Top Breadcrumb
      const bc = document.getElementById('top-breadcrumb');
      if (tab === 'env') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981] flex-shrink-0"></span> Environment & Diagnostics';
      } else if (tab === 'search') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-[#3B82F6] shadow-[0_0_6px_#3B82F6] flex-shrink-0"></span> Fast Search (Everything Engine)';
        initSearchTab();
      } else if (tab === 'ports') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-[#06B6D4] shadow-[0_0_6px_#06B6D4] flex-shrink-0"></span> Port Manager & Sockets';
        fetchPorts();
      } else if (tab === 'project') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-[#8B5CF6] shadow-[0_0_6px_#8B5CF6] flex-shrink-0"></span> Project Workstation Auditor';
        renderRecentProjects();
      } else if (tab === 'settings') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-[#94A3B8] flex-shrink-0"></span> Preferences & Search Roots';
        loadConfig();
        loadSystemInfo();
        fetchSearchTelemetry();
      }
    }

    function refreshActiveTab() {
      lastScanTime = Date.now();
      updateTimerDisplay();
      if (activeTab === 'env') fetchAudit();
      else if (activeTab === 'search') triggerSearch(false);
      else if (activeTab === 'ports') fetchPorts();
      else if (activeTab === 'project') runProjectAudit();
      else if (activeTab === 'settings') { loadConfig(); loadSystemInfo(); fetchSearchTelemetry(); }
    }

    function updateTimerDisplay() {
      const elapsedSec = Math.round((Date.now() - lastScanTime) / 1000);
      const timerEl = document.getElementById('rescan-timer');
      if (elapsedSec < 60) {
        timerEl.innerText = '(now)';
      } else {
        timerEl.innerText = `(${Math.floor(elapsedSec / 60)}m)`;
      }
    }
    setInterval(updateTimerDisplay, 30000);

    // ==================== EXPORT REPORT LOGIC ====================
    function toggleExportMenu() {
      const menu = document.getElementById('export-menu');
      if (menu) menu.classList.toggle('hidden');
    }

    function closeExportMenu() {
      const menu = document.getElementById('export-menu');
      if (menu && !menu.classList.contains('hidden')) menu.classList.add('hidden');
    }

    document.addEventListener('click', (e) => {
      const wrapper = document.getElementById('export-dropdown-wrapper');
      if (wrapper && !wrapper.contains(e.target)) {
        closeExportMenu();
      }
    });

    function exportReport(type) {
      closeExportMenu();
      if (allReports.length === 0) {
        showToast('No audit data available to export', true);
        return;
      }

      if (type === 'json') {
        const payload = {
          generated_at: new Date().toISOString(),
          total_tools: allReports.length,
          reports: allReports
        };
        copyToClipboard(JSON.stringify(payload, null, 2), 'JSON report');
        return;
      }

      // Markdown Format
      const installed = allReports.filter(r => r.installed).length;
      const healthy = allReports.filter(r => r.status === 'healthy').length;
      const warning = allReports.filter(r => r.status === 'warning').length;

      let md = `# DevToolkit Workstation Environment Audit\n\n`;
      md += `- **Generated At**: ${new Date().toLocaleString()}\n`;
      md += `- **Tools Audited**: ${allReports.length} | **Installed**: ${installed} | **Healthy**: ${healthy} | **Action Needed**: ${warning}\n\n`;
      md += `| Tool | Categories | Status | Version | Root / Home Path | Binary Executable |\n`;
      md += `| :--- | :--- | :--- | :--- | :--- | :--- |\n`;

      allReports.forEach(r => {
        const cats = (r.categories && r.categories.length > 0) ? r.categories.join(', ') : r.category;
        const stat = r.status.toUpperCase();
        const ver = r.version ? ('v' + r.version) : (r.installed ? 'Installed' : 'Not Detected');
        const home = r.home_path ? `\`${r.home_path}\`` : '—';
        const bin = r.binary_path ? `\`${r.binary_path}\`` : '—';
        md += `| **${r.name}** | ${cats} | ${stat} | ${ver} | ${home} | ${bin} |\n`;
      });

      const warnings = allReports.filter(r => r.diagnostics && r.diagnostics.length > 0);
      if (warnings.length > 0) {
        md += `\n## Diagnostics & Action Items\n\n`;
        warnings.forEach(r => {
          md += `### ${r.name}\n`;
          r.diagnostics.forEach(d => {
            md += `- **Issue**: ${d.message}\n`;
            if (d.suggested_fix) {
              md += `  - **Suggested Fix**: \`${d.suggested_fix}\`\n`;
            }
          });
          md += `\n`;
        });
      }

      if (type === 'md') {
        copyToClipboard(md, 'Markdown report');
      } else if (type === 'download') {
        const blob = new Blob([md], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `devtoolkit-audit-${new Date().toISOString().slice(0, 10)}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Downloaded audit report as Markdown');
      }
    }

    // ==================== SLIDE-OVER INSPECTOR DRAWER ====================
    let deepReportCache = {};
    let deepReportLoading = {};

    function openInspectorDrawer(toolId) {
      activeDrawerToolId = toolId;
      renderInspectorDrawer(toolId);
      const drawer = document.getElementById('inspector-drawer');
      const backdrop = document.getElementById('inspector-backdrop');
      const panel = document.getElementById('inspector-panel');

      drawer.classList.remove('hidden');
      setTimeout(() => {
        backdrop.classList.remove('opacity-0');
        backdrop.classList.add('opacity-100');
        panel.classList.add('open');
      }, 10);

      // Trigger on-demand deep inspection probe if not cached
      if (!deepReportCache[toolId] && !deepReportLoading[toolId]) {
        fetchDeepTelemetry(toolId);
      }
    }

    function closeInspectorDrawer() {
      const backdrop = document.getElementById('inspector-backdrop');
      const panel = document.getElementById('inspector-panel');
      const drawer = document.getElementById('inspector-drawer');

      backdrop.classList.remove('opacity-100');
      backdrop.classList.add('opacity-0');
      panel.classList.remove('open');

      setTimeout(() => {
        drawer.classList.add('hidden');
        activeDrawerToolId = null;
      }, 280);
    }

    async function fetchDeepTelemetry(toolId, forceRefresh = false) {
      if (deepReportLoading[toolId]) return;
      deepReportLoading[toolId] = true;
      if (forceRefresh) {
        delete deepReportCache[toolId];
      }
      if (activeDrawerToolId === toolId) {
        renderInspectorDrawer(toolId);
      }
      try {
        const res = await fetch(`/api/tool/${toolId}/deep`);
        if (res.ok) {
          const data = await res.json();
          deepReportCache[toolId] = data;
        } else {
          console.warn(`Deep inspection endpoint returned ${res.status} for ${toolId}`);
        }
      } catch (err) {
        console.error(`Failed to fetch deep telemetry for ${toolId}:`, err);
      } finally {
        deepReportLoading[toolId] = false;
        if (activeDrawerToolId === toolId) {
          renderInspectorDrawer(toolId);
        }
      }
    }

    function downloadDeepReport(toolId) {
      const r = allReports.find(x => x.id === toolId);
      const deep = deepReportCache[toolId];
      const payload = {
        generated_at: new Date().toISOString(),
        tool: r || null,
        deep_telemetry: deep || null,
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${toolId}_diagnostic_report.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast(`Downloaded ${toolId} diagnostic bundle`);
    }

    function renderInspectorDrawer(toolId) {
      const container = document.getElementById('inspector-content');
      const r = allReports.find(x => x.id === toolId);
      if (!r) {
        container.innerHTML = '<div class="p-6 text-[#94A3B8]">Tool details not found.</div>';
        return;
      }
      if (r.scanning) {
        container.innerHTML = `
          <div class="p-8 text-center space-y-4">
            <div class="w-10 h-10 mx-auto rounded bg-[#06B6D41A] border border-[#06B6D440] flex items-center justify-center text-[#06B6D4] text-lg">
              <i class="fa-solid fa-circle-notch fa-spin"></i>
            </div>
            <div>
              <h3 class="text-[#F3F4F6] font-semibold text-sm">Inspecting ${r.name}...</h3>
              <p class="text-[#94A3B8] text-xs mt-1">Environment inspection is currently running for this tool.</p>
            </div>
          </div>
        `;
        return;
      }

      const deep = deepReportCache[toolId];
      const isLoadingDeep = deepReportLoading[toolId];

      const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category];
      const categoriesHtml = toolCats.map(c => 
        `<span class="text-[10px] text-[#94A3B8] uppercase tracking-wider font-mono font-medium px-2 py-0.5 bg-[#141721] rounded border border-[#1F2430]">${c}</span>`
      ).join('');

      const cleanHome = (r.home_path || '').replace(/"/g, '&quot;');
      const cleanBin = (r.binary_path || '').replace(/"/g, '&quot;');
      const cleanVer = (r.version || '').replace(/"/g, '&quot;');

      // Precedence tag
      let precedenceTag = '';
      if (r.installed) {
        if (r.binary_path && (r.binary_path.toLowerCase().includes('windowsapps') || r.binary_path.toLowerCase().includes('portable'))) {
          precedenceTag = '<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 font-medium">Portable / Standalone</span>';
        } else {
          precedenceTag = '<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/30 font-medium">Active in PATH</span>';
        }
      }

      // ZONE 2: Diagnostics & Recommended Actions (NO 1-click apply, clean copyable commands)
      let diagHtml = '';
      if (r.diagnostics && r.diagnostics.length > 0) {
        diagHtml = r.diagnostics.map(d => {
          const cleanFix = (d.suggested_fix || '').replace(/"/g, '&quot;');
          return `
            <div class="p-3.5 rounded bg-[#F59E0B0D] border border-[#F59E0B33] text-[#F59E0B] text-xs space-y-2.5">
              <div class="flex items-start gap-2 font-medium leading-relaxed">
                <i class="fa-solid fa-triangle-exclamation text-[#F59E0B] mt-0.5 text-xs flex-shrink-0"></i>
                <span>${d.message}</span>
              </div>
              ${d.suggested_fix ? `
                <div class="bg-[#08090C] p-2.5 rounded border border-[#1F2430] space-y-2">
                  <div class="text-[10px] uppercase font-mono tracking-wider font-semibold text-[#F59E0B]">Remediation Command:</div>
                  <div class="flex items-center justify-between gap-2 font-mono text-[11px] text-[#F3F4F6] min-w-0">
                    <code class="truncate bg-[#141721] px-2 py-1 rounded border border-[#1F2430] flex-1 select-text">${d.suggested_fix}</code>
                    <button onclick="copyToClipboard(this.dataset.cmd, 'command')" data-cmd="${cleanFix}" class="btn-secondary-pro px-2.5 py-1 text-[11px] font-mono flex items-center gap-1.5 flex-shrink-0 hover:border-[#10B981]/50 hover:text-[#10B981]">
                      <i class="fa-regular fa-copy"></i> Copy
                    </button>
                  </div>
                </div>
              ` : ''}
            </div>
          `;
        }).join('');
      } else if (r.status === 'healthy') {
        diagHtml = `
          <div class="p-3 rounded bg-[#10B9810D] border border-[#10B98133] text-[#10B981] text-xs flex items-center gap-2.5">
            <i class="fa-solid fa-circle-check text-sm text-[#10B981] flex-shrink-0"></i>
            <div>
              <div class="font-semibold">Workstation Ready</div>
              <div class="text-[11px] text-[#94A3B8] mt-0.5">All path registrations and core companions are operating optimally.</div>
            </div>
          </div>
        `;
      } else {
        diagHtml = `
          <div class="p-3 rounded bg-[#141721] border border-[#1F2430] text-[#94A3B8] text-xs flex items-center gap-2.5">
            <i class="fa-solid fa-circle-info text-sm text-[#475569] flex-shrink-0"></i>
            <div>
              <div class="font-semibold text-[#F3F4F6]">Tool Not Detected</div>
              <div class="text-[11px] text-[#94A3B8] mt-0.5">This tool was not detected in system PATH, registry, or custom search roots.</div>
            </div>
          </div>
        `;
      }

      // ZONE 3: Monitored Environment Variables Table
      let envVarsHtml = '';
      if (deep && deep.env_vars && deep.env_vars.length > 0) {
        envVarsHtml = `
          <div class="space-y-1.5">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider">Monitored Environment Variables</div>
            <div class="bg-[#08090C] rounded border border-[#1F2430] overflow-hidden divide-y divide-[#1F2430]">
              ${deep.env_vars.map(ev => {
                let badgeClass = 'badge-aligned';
                let iconClass = 'fa-check';
                if (ev.status === 'divergent') {
                  badgeClass = 'badge-divergent';
                  iconClass = 'fa-triangle-exclamation';
                } else if (ev.status === 'missing') {
                  badgeClass = 'badge-missing';
                  iconClass = 'fa-xmark';
                }
                const cleanVal = (ev.value || '').replace(/"/g, '&quot;');
                return `
                  <div class="p-2.5 flex items-start justify-between gap-3 text-xs hover:bg-[#141721]/40 transition">
                    <div class="min-w-0 space-y-0.5">
                      <div class="flex items-center gap-2">
                        <span class="font-mono font-semibold text-[#F3F4F6] text-[11px]">${ev.name}</span>
                        <span class="${badgeClass} px-1.5 py-0.2 rounded text-[9px] font-mono font-semibold uppercase inline-flex items-center gap-1">
                          <i class="fa-solid ${iconClass} text-[8px]"></i> ${ev.status}
                        </span>
                      </div>
                      <div class="font-mono text-[10px] text-slate-400 truncate select-text" title="${ev.value || 'Not configured'}">
                        ${ev.value ? `<code>${ev.value}</code>` : '<span class="text-slate-600 italic">Unset</span>'}
                      </div>
                      ${ev.message ? `<div class="text-[10px] text-slate-400">${ev.message}</div>` : ''}
                    </div>
                    ${ev.value ? `
                      <button onclick="copyToClipboard('${cleanVal}', '${ev.name}')" class="btn-secondary-pro px-2 py-0.5 text-[9px] font-mono flex-shrink-0 hover:text-[#06B6D4]">
                        <i class="fa-regular fa-copy"></i>
                      </button>
                    ` : ''}
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        `;
      }

      // ZONE 4: Ecosystem & Companion Subsystems Matrix
      let companionsHtml = '';
      if (r.companions && r.companions.length > 0) {
        companionsHtml = `
          <div class="space-y-2">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider flex items-center justify-between">
              <span>Ecosystem Companions</span>
              <span class="font-mono text-[#94A3B8]">${r.companions.filter(c => c.installed).length}/${r.companions.length} Available</span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
              ${r.companions.map(c => `
                <div class="p-2 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-between text-xs">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="w-4 h-4 rounded flex items-center justify-center text-[10px] ${c.installed ? 'bg-[#10B9811A] text-[#10B981]' : 'bg-[#141721] text-[#475569]'}">
                      <i class="fa-solid ${c.installed ? 'fa-check' : 'fa-xmark'}"></i>
                    </span>
                    <span class="font-medium text-[#F3F4F6] truncate">${c.name}</span>
                  </div>
                  <span class="font-mono text-[10px] text-[#94A3B8] flex-shrink-0">${c.version ? 'v' + c.version : (c.installed ? 'detected' : 'missing')}</span>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }

      // ZONE 5: Deep Domain Telemetry (On-demand with shimmer loader)
      let deepTelemetryHtml = '';
      if (isLoadingDeep && !deep) {
        deepTelemetryHtml = `
          <div class="space-y-2">
            <div class="flex items-center justify-between text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider">
              <span class="flex items-center gap-1.5"><i class="fa-solid fa-microchip text-[#06B6D4]"></i> Deep Domain Telemetry</span>
              <span class="text-[#06B6D4] text-[10px] font-mono flex items-center gap-1"><i class="fa-solid fa-spinner fa-spin"></i> Probing...</span>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div class="h-16 rounded bg-[#0E1015] border border-[#1F2430] skeleton-shimmer"></div>
              <div class="h-16 rounded bg-[#0E1015] border border-[#1F2430] skeleton-shimmer"></div>
              <div class="h-16 rounded bg-[#0E1015] border border-[#1F2430] skeleton-shimmer"></div>
              <div class="h-16 rounded bg-[#0E1015] border border-[#1F2430] skeleton-shimmer"></div>
            </div>
          </div>
        `;
      } else if (deep && deep.telemetry && Object.keys(deep.telemetry).length > 0) {
        const tiles = Object.entries(deep.telemetry).filter(([k, v]) => v !== null && v !== undefined && typeof v !== 'object');
        if (tiles.length > 0) {
          deepTelemetryHtml = `
            <div class="space-y-2">
              <div class="flex items-center justify-between text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider">
                <span class="flex items-center gap-1.5"><i class="fa-solid fa-microchip text-[#06B6D4]"></i> Deep Domain Telemetry</span>
                <span class="text-[10px] font-mono text-[#06B6D4] bg-[#06B6D4]/10 border border-[#06B6D4]/30 px-1.5 py-0.2 rounded flex items-center gap-1">
                  <i class="fa-solid fa-bolt text-[9px]"></i> ${deep.probe_latency_ms}ms
                </span>
              </div>
              <div class="grid grid-cols-2 sm:grid-cols-2 gap-2">
                ${tiles.map(([k, v]) => `
                  <div class="p-2.5 rounded bg-[#08090C] border border-[#1F2430] space-y-1">
                    <div class="text-[10px] font-mono text-slate-500 uppercase tracking-wider truncate">${k.replace(/_/g, ' ')}</div>
                    <div class="font-mono text-xs text-[#F3F4F6] font-semibold truncate select-text" title="${String(v)}">${String(v)}</div>
                  </div>
                `).join('')}
              </div>
            </div>
          `;
        }
      }

      // ZONE 6: Discovered Installations & Multi-Instance Precedence
      let instancesHtml = '';
      if (isLoadingDeep && !deep) {
        instancesHtml = `
          <div class="space-y-2">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider flex items-center justify-between">
              <span>Discovered Installations & Precedence</span>
            </div>
            <div class="h-20 rounded bg-[#0E1015] border border-[#1F2430] skeleton-shimmer"></div>
          </div>
        `;
      } else if (deep && deep.instances && deep.instances.length > 0) {
        instancesHtml = `
          <div class="space-y-2">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider flex items-center justify-between">
              <span>Discovered Installations & Precedence</span>
              <span class="font-mono text-[#94A3B8]">${deep.instances.length} Located</span>
            </div>
            <div class="bg-[#08090C] rounded border border-[#1F2430] divide-y divide-[#1F2430] overflow-hidden">
              ${deep.instances.map(inst => {
                const cleanInstPath = (inst.path || '').replace(/"/g, '&quot;');
                const cleanInstBin = (inst.binary_path || inst.path || '').replace(/"/g, '&quot;');
                return `
                  <div class="p-3 hover:bg-[#141721]/50 transition space-y-1.5 text-xs">
                    <div class="flex items-center justify-between gap-2">
                      <div class="flex items-center gap-2 min-w-0">
                        ${inst.is_active
                          ? '<span class="instance-active-badge px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold uppercase flex items-center gap-1 flex-shrink-0"><i class="fa-solid fa-circle-check text-[8px]"></i> Active in PATH</span>'
                          : `<span class="text-slate-400 bg-[#141721] border border-[#1F2430] px-1.5 py-0.5 rounded text-[9px] font-mono uppercase flex-shrink-0">${inst.source}</span>`
                        }
                        ${inst.version ? `<span class="font-mono text-[10px] text-[#06B6D4] font-medium truncate">v${inst.version}</span>` : ''}
                      </div>
                      <div class="flex items-center gap-1 flex-shrink-0">
                        <button onclick="copyToClipboard('${cleanInstBin}', 'installation path')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1" title="Copy Path">
                          <i class="fa-regular fa-copy text-[9px]"></i> Copy
                        </button>
                        <button onclick="openFolder('${cleanInstPath}')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1 hover:text-[#06B6D4]" title="Open Folder">
                          <i class="fa-regular fa-folder-open text-[9px]"></i> Open
                        </button>
                      </div>
                    </div>
                    <div class="font-mono text-[11px] text-[#F3F4F6] break-all select-text bg-[#0E1015] p-1.5 rounded border border-[#1F2430]">
                      ${inst.binary_path || inst.path}
                    </div>
                    ${inst.details ? `<div class="text-[10px] text-slate-400">${inst.details}</div>` : ''}
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        `;
      }

      // ZONE 7: Diagnostic Telemetry Bundle & Raw Data (Enhanced JSON)
      const rawDumpKeys = deep && deep.raw_dumps ? Object.keys(deep.raw_dumps) : [];
      const bundlePayload = {
        tool: r,
        deep_telemetry: deep || null,
      };

      container.innerHTML = `
        <!-- Drawer Header -->
        <div class="p-4 sm:p-5 border-b border-[#1F2430] flex items-start justify-between gap-3 bg-[#08090C]">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-10 h-10 rounded bg-[#141721] border border-[#1F2430] flex items-center justify-center text-xl flex-shrink-0 shadow">
              ${getToolIcon(r.id, r.category)}
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <h2 class="text-base font-semibold text-[#F3F4F6] tracking-tight truncate">${r.name}</h2>
                ${precedenceTag}
              </div>
              <div class="flex items-center gap-2 mt-1">
                ${r.version ? `
                  <button onclick="copyToClipboard('${cleanVer}', 'version')" class="text-xs font-mono font-medium text-[#06B6D4] bg-[#06B6D4]/10 hover:bg-[#06B6D4]/20 border border-[#06B6D4]/30 px-1.5 py-0.5 rounded transition flex items-center gap-1" title="Click to copy version">
                    <span>v${r.version}</span>
                    <i class="fa-regular fa-copy text-[9px] text-[#06B6D4]/70"></i>
                  </button>
                ` : `<span class="text-xs font-mono text-slate-500">${r.installed ? 'Detected' : 'Not Found'}</span>`}
                <span class="text-[#2E3446]">•</span>
                <div class="flex items-center gap-1">${categoriesHtml}</div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <button onclick="fetchDeepTelemetry('${r.id}', true)" class="p-1.5 rounded text-[#94A3B8] hover:text-[#06B6D4] hover:bg-[#141721] transition" title="Re-probe deep telemetry">
              <i class="fa-solid fa-arrows-rotate text-xs ${isLoadingDeep ? 'fa-spin text-[#06B6D4]' : ''}"></i>
            </button>
            ${getBadge(r.status)}
            <button onclick="closeInspectorDrawer()" class="p-1.5 rounded text-[#94A3B8] hover:text-[#F3F4F6] hover:bg-[#141721] transition" title="Close Drawer (Esc)">
              <i class="fa-solid fa-xmark text-sm"></i>
            </button>
          </div>
        </div>

        <!-- Drawer Body -->
        <div class="flex-1 overflow-y-auto p-4 sm:p-5 space-y-5 custom-scrollbar font-sans">
          <!-- ZONE 2: Diagnostics / Health Status Card -->
          <div class="space-y-1.5">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider">Health Status & Recommended Actions</div>
            ${diagHtml}
          </div>

          <!-- ZONE 3: Filesystem & Locations -->
          <div class="space-y-2.5">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider">Filesystem & Runtime Paths</div>
            
            <!-- Root Path -->
            <div class="bg-[#0E1015] p-3 rounded border border-[#1F2430] space-y-1.5">
              <div class="flex items-center justify-between text-[11px] text-[#94A3B8]">
                <span class="font-mono font-medium text-[#06B6D4] uppercase tracking-wider text-[10px]"><i class="fa-solid fa-folder text-xs mr-1"></i> Root / Home Directory</span>
                <div class="flex items-center gap-1">
                  ${r.home_path ? `
                    <button onclick="copyToClipboard('${cleanHome}', 'root path')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1">
                      <i class="fa-regular fa-copy text-[9px]"></i> Copy
                    </button>
                    <button onclick="openFolder('${cleanHome}')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1 hover:text-[#06B6D4]">
                      <i class="fa-regular fa-folder-open text-[9px]"></i> Open
                    </button>
                  ` : ''}
                </div>
              </div>
              <div class="font-mono text-xs text-[#F3F4F6] break-all select-text bg-[#08090C] p-2 rounded border border-[#1F2430]">
                ${r.home_path || '<span class="text-[#475569] italic">Not detected or not applicable</span>'}
              </div>
            </div>

            <!-- Binary Path -->
            <div class="bg-[#0E1015] p-3 rounded border border-[#1F2430] space-y-1.5">
              <div class="flex items-center justify-between text-[11px] text-[#94A3B8]">
                <span class="font-mono font-medium text-[#10B981] uppercase tracking-wider text-[10px]"><i class="fa-solid fa-terminal text-xs mr-1"></i> Primary Executable Binary</span>
                <div class="flex items-center gap-1">
                  ${r.binary_path ? `
                    <button onclick="copyToClipboard('${cleanBin}', 'binary path')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1">
                      <i class="fa-regular fa-copy text-[9px]"></i> Copy
                    </button>
                    <button onclick="openFolder('${cleanBin}')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1 hover:text-[#10B981]">
                      <i class="fa-regular fa-folder-open text-[9px]"></i> Open
                    </button>
                  ` : ''}
                </div>
              </div>
              <div class="font-mono text-xs text-[#F3F4F6] break-all select-text bg-[#08090C] p-2 rounded border border-[#1F2430]">
                ${r.binary_path || '<span class="text-[#475569] italic">Not detected in system PATH</span>'}
              </div>
            </div>

            <!-- Monitored Environment Variables Alignment -->
            ${envVarsHtml}
          </div>

          <!-- ZONE 4: Companions Matrix -->
          ${companionsHtml}

          <!-- ZONE 5: Deep Domain Telemetry -->
          ${deepTelemetryHtml}

          <!-- ZONE 6: Multi-Instance Discovery -->
          ${instancesHtml}

          <!-- ZONE 7: Collapsible Diagnostic Telemetry Bundle (JSON) -->
          <details class="text-xs bg-[#0E1015] rounded border border-[#1F2430] p-3 group">
            <summary class="font-medium text-[#94A3B8] hover:text-[#F3F4F6] cursor-pointer flex items-center justify-between select-none">
              <div class="flex items-center gap-2">
                <i class="fa-solid fa-file-code text-[#06B6D4]"></i>
                <span class="font-semibold text-white">Diagnostic Telemetry Bundle (JSON)</span>
                ${deep ? `<span class="text-[10px] font-mono text-slate-500">(${rawDumpKeys.length} raw dumps • ${deep.discovery_trace?.length || 0} trace steps)</span>` : ''}
              </div>
              <span class="text-[10px] text-[#06B6D4] group-open:rotate-180 transition-transform"><i class="fa-solid fa-chevron-down"></i></span>
            </summary>
            <div class="mt-3 space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="text-[11px] text-slate-400 font-mono">Enriched machine-readable diagnostic bundle</span>
                <div class="flex items-center gap-1.5">
                  <button onclick="copyToClipboard(JSON.stringify(deepReportCache['${r.id}'] || allReports.find(x => x.id === '${r.id}'), null, 2), 'telemetry JSON')" class="btn-secondary-pro px-2.5 py-1 text-[10px] font-mono flex items-center gap-1">
                    <i class="fa-regular fa-copy"></i> Copy JSON
                  </button>
                  <button onclick="downloadDeepReport('${r.id}')" class="btn-secondary-pro px-2.5 py-1 text-[10px] font-mono flex items-center gap-1 hover:text-[#10B981]">
                    <i class="fa-solid fa-download"></i> Download Report
                  </button>
                </div>
              </div>
              <pre class="bg-[#08090C] p-3 rounded border border-[#1F2430] font-mono text-[10px] text-[#94A3B8] overflow-x-auto custom-scrollbar select-text max-h-[360px]">${JSON.stringify(bundlePayload, null, 2)}</pre>
            </div>
          </details>
        </div>
      `;
    }

    // ==================== TAB 1: ENVIRONMENT & AUDITING ====================
    const DOMAIN_CATEGORIES = [
      { id: 'all', label: 'All', icon: 'fa-cubes' },
      { id: 'runtime', label: 'Runtimes', icon: 'fa-terminal', match: ['runtime', 'framework', 'language'] },
      { id: 'ide', label: 'IDEs & Editors', icon: 'fa-code', match: ['ide', 'editor'] },
      { id: 'build', label: 'Build & Tools', icon: 'fa-screwdriver-wrench', match: ['build', 'tools', 'compiler'] },
      { id: 'vcs', label: 'VCS & Git', icon: 'fa-code-branch', match: ['vcs', 'scm', 'cli'] },
      { id: 'mobile', label: 'Mobile & SDKs', icon: 'fa-mobile-screen', match: ['mobile', 'sdk'] },
      { id: 'container', label: 'Cloud & Containers', icon: 'fa-cloud', match: ['container', 'devops', 'cloud', 'iac'] },
      { id: 'database', label: 'Databases', icon: 'fa-database', match: ['database', 'cache', 'sql'] },
      { id: 'ai', label: 'AI & ML', icon: 'fa-brain', match: ['ai', 'ml', 'hardware'] },
    ];

    function getToolIcon(id, category) {
      if (id === 'docker') return '<i class="fa-brands fa-docker text-[#06B6D4]"></i>';
      if (id === 'android_studio') return '<i class="fa-brands fa-android text-[#10B981]"></i>';
      if (id === 'android') return '<i class="fa-solid fa-mobile-screen-button text-[#F59E0B]"></i>';
      if (id === 'node') return '<i class="fa-brands fa-node-js text-[#10B981]"></i>';
      if (id === 'git') return '<i class="fa-brands fa-git-alt text-[#F59E0B]"></i>';
      if (id === 'python') return '<i class="fa-brands fa-python text-[#F59E0B]"></i>';
      if (id === 'java') return '<i class="fa-brands fa-java text-[#EF4444]"></i>';
      if (id === 'flutter') return '<i class="fa-solid fa-feather-pointed text-[#06B6D4]"></i>';
      if (id === 'golang') return '<i class="fa-brands fa-golang text-[#06B6D4]"></i>';
      if (id === 'rust') return '<i class="fa-brands fa-rust text-[#F59E0B]"></i>';
      if (id === 'vscode') return '<i class="fa-solid fa-code text-[#06B6D4]"></i>';
      if (id === 'dotnet') return '<i class="fa-brands fa-microsoft text-[#8B5CF6]"></i>';
      if (id === 'bun') return '<i class="fa-solid fa-bread-slice text-[#F59E0B]"></i>';
      if (id === 'gh') return '<i class="fa-brands fa-github text-[#F3F4F6]"></i>';
      if (id === 'cmake') return '<i class="fa-solid fa-screwdriver-wrench text-[#EF4444]"></i>';
      if (id === 'ollama') return '<i class="fa-solid fa-brain text-[#8B5CF6]"></i>';
      if (id === 'kubectl') return '<i class="fa-solid fa-dharmachakra text-[#06B6D4]"></i>';
      if (id === 'terraform') return '<i class="fa-solid fa-layer-group text-[#8B5CF6]"></i>';
      if (id === 'c_compiler') return '<i class="fa-solid fa-c text-[#06B6D4]"></i>';
      if (id === 'php') return '<i class="fa-brands fa-php text-[#8B5CF6]"></i>';
      if (id === 'cuda') return '<i class="fa-solid fa-microchip text-[#10B981]"></i>';
      if (id === 'sqlite') return '<i class="fa-solid fa-database text-[#06B6D4]"></i>';
      if (category === 'runtime') return '<i class="fa-solid fa-terminal text-[#06B6D4]"></i>';
      if (category === 'ide') return '<i class="fa-solid fa-code text-[#8B5CF6]"></i>';
      if (category === 'build') return '<i class="fa-solid fa-screwdriver-wrench text-[#F59E0B]"></i>';
      if (category === 'ai') return '<i class="fa-solid fa-brain text-[#8B5CF6]"></i>';
      if (category === 'database') return '<i class="fa-solid fa-database text-[#06B6D4]"></i>';
      if (category === 'cloud') return '<i class="fa-solid fa-cloud text-[#06B6D4]"></i>';
      return '<i class="fa-solid fa-cube text-[#94A3B8]"></i>';
    }

    function getBadge(status) {
      if (status === 'scanning') {
        return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#06B6D41A] text-[#06B6D4] border border-[#06B6D440] whitespace-nowrap animate-pulse"><i class="fa-solid fa-circle-notch fa-spin text-[9px]"></i> Scanning</span>';
      }
      if (status === 'healthy') {
        return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#10B9811A] text-[#10B981] border border-[#10B98140] whitespace-nowrap"><span class="w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981]"></span> Healthy</span>';
      }
      if (status === 'warning') {
        return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#F59E0B1A] text-[#F59E0B] border border-[#F59E0B40] whitespace-nowrap"><i class="fa-solid fa-triangle-exclamation text-[9px]"></i> Action Needed</span>';
      }
      if (status === 'error') {
        return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#EF44441A] text-[#EF4444] border border-[#EF444440] whitespace-nowrap"><i class="fa-solid fa-xmark text-[9px]"></i> Error</span>';
      }
      return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#141721] text-[#94A3B8] border border-[#1F2430] whitespace-nowrap"><span class="w-1.5 h-1.5 rounded-full bg-[#475569]"></span> Not Detected</span>';
    }

    function toolMatchesCategory(r, cat) {
      if (!cat || cat === 'all') return true;
      const domain = DOMAIN_CATEGORIES.find(d => d.id === cat);
      const cats = (r.categories && r.categories.length > 0) 
        ? r.categories.map(c => c.toLowerCase()) 
        : [(r.category || '').toLowerCase()];
      
      if (domain && domain.match) {
        return domain.match.some(m => cats.includes(m.toLowerCase()) || cats.some(c => c.includes(m.toLowerCase())));
      }
      return cats.includes(cat.toLowerCase());
    }

    // Interactive Metric Stat Filter Cards
    function toggleStatusFilter(status) {
      if (status === 'all' || currentStatusFilter === status) {
        currentStatusFilter = null;
      } else {
        currentStatusFilter = status;
      }
      updateStatusFilterUI();
      renderTools();
    }

    function clearStatusFilter() {
      currentStatusFilter = null;
      updateStatusFilterUI();
      renderTools();
    }

    function resetAllFilters() {
      currentCategory = 'all';
      currentStatusFilter = null;
      const searchInput = document.getElementById('global-search-input');
      if (searchInput) searchInput.value = '';
      try {
        localStorage.setItem('devtoolkit_last_category', 'all');
      } catch (e) {}
      renderCategoryPills();
      updateStatusFilterUI();
      renderTools();
      showToast('Filters reset to default view');
    }

    function updateStatusFilterUI() {
      const cardIds = ['all', 'installed', 'healthy', 'warning', 'error', 'not_found'];
      cardIds.forEach(id => {
        const el = document.getElementById(`stat-card-${id}`);
        if (el) {
          if (currentStatusFilter === id) {
            el.classList.add('stat-filter-active');
          } else {
            el.classList.remove('stat-filter-active');
          }
        }
      });

      const pillContainer = document.getElementById('active-status-pill-container');
      const pillLabel = document.getElementById('active-status-pill-label');
      const resetBtn = document.getElementById('reset-filters-btn');

      const labels = {
        'installed': 'Installed Tools',
        'healthy': 'Healthy Only',
        'warning': 'Action Needed',
        'error': 'Errors Only',
        'not_found': 'Not Detected'
      };

      if (currentStatusFilter && labels[currentStatusFilter]) {
        pillLabel.innerText = `Status: ${labels[currentStatusFilter]}`;
        pillContainer.classList.remove('hidden');
        pillContainer.classList.add('flex');
      } else {
        pillContainer.classList.add('hidden');
        pillContainer.classList.remove('flex');
      }

      const query = (document.getElementById('global-search-input')?.value || '').trim();
      if (currentStatusFilter !== null || currentCategory !== 'all' || query.length > 0) {
        resetBtn.classList.remove('hidden');
      } else {
        resetBtn.classList.add('hidden');
      }
    }

    function renderCategoryPills() {
      const container = document.getElementById('category-filters');
      if (!container) return;

      container.innerHTML = DOMAIN_CATEGORIES.map(domain => {
        const count = domain.id === 'all' 
          ? allReports.length 
          : allReports.filter(r => toolMatchesCategory(r, domain.id)).length;
        const isActive = currentCategory === domain.id;
        const activeClass = 'cat-btn px-2.5 py-1 rounded text-xs font-medium bg-[#141721] text-white border border-[#10B98180] shadow-sm transition flex-shrink-0 flex items-center gap-1.5';
        const inactiveClass = 'cat-btn px-2.5 py-1 rounded text-xs font-medium text-[#94A3B8] hover:text-[#F3F4F6] hover:bg-[#141721] border border-transparent transition flex-shrink-0 flex items-center gap-1.5';
        
        return `
          <button onclick="setCategory('${domain.id}')" class="${isActive ? activeClass : inactiveClass}" data-cat="${domain.id}">
            <i class="fa-solid ${domain.icon} text-[10px] ${isActive ? 'text-[#10B981]' : 'text-[#475569]'}"></i>
            <span>${domain.label}</span>
            <span class="ml-0.5 text-[10px] font-mono ${isActive ? 'text-[#10B981] font-semibold' : 'text-[#475569]'}">${count}</span>
          </button>
        `;
      }).join('');
    }

    function setCategory(cat) {
      currentCategory = cat;
      try {
        localStorage.setItem('devtoolkit_last_category', cat);
      } catch (e) {}
      renderCategoryPills();
      updateStatusFilterUI();
      renderTools();
    }

    function setLayout(mode) {
      currentLayout = mode;
      const gridBtn = document.getElementById('layout-grid-btn');
      const listBtn = document.getElementById('layout-list-btn');
      const gridEl = document.getElementById('tools-grid');
      const listEl = document.getElementById('tools-list-container');

      if (mode === 'grid') {
        gridBtn.className = 'p-1 rounded text-xs bg-[#141721] text-[#10B981] border border-[#10B98140] transition';
        listBtn.className = 'p-1 rounded text-xs text-[#94A3B8] hover:text-[#F3F4F6] transition';
        gridEl.classList.remove('hidden');
        listEl.classList.add('hidden');
      } else {
        gridBtn.className = 'p-1 rounded text-xs text-[#94A3B8] hover:text-[#F3F4F6] transition';
        listBtn.className = 'p-1 rounded text-xs bg-[#141721] text-[#10B981] border border-[#10B98140] transition';
        gridEl.classList.add('hidden');
        listEl.classList.remove('hidden');
      }
      renderTools();
    }

    function onSortChange() {
      currentSort = document.getElementById('sort-select').value;
      renderTools();
    }

    function onSearchChange() {
      updateStatusFilterUI();
      renderTools();
    }

    function renderTools() {
      const query = (document.getElementById('global-search-input')?.value || '').toLowerCase().trim();
      let filtered = allReports.filter(r => {
        const matchesCat = toolMatchesCategory(r, currentCategory);
        let matchesStatus = true;
        if (currentStatusFilter === 'installed') {
          matchesStatus = r.installed === true;
        } else if (currentStatusFilter) {
          matchesStatus = r.status === currentStatusFilter;
        }

        const cats = (r.categories && r.categories.length > 0) ? r.categories.map(c => c.toLowerCase()) : [r.category.toLowerCase()];
        const matchesQuery = !query ||
          r.name.toLowerCase().includes(query) ||
          r.id.toLowerCase().includes(query) ||
          cats.some(c => c.includes(query)) ||
          (r.version && r.version.toLowerCase().includes(query)) ||
          (r.binary_path && r.binary_path.toLowerCase().includes(query)) ||
          (r.home_path && r.home_path.toLowerCase().includes(query));
        return matchesCat && matchesStatus && matchesQuery;
      });

      // Sort logic
      filtered.sort((a, b) => {
        if (currentSort === 'severity') {
          const weight = { 'error': 4, 'warning': 3, 'not_found': 2, 'healthy': 1 };
          return (weight[b.status] || 0) - (weight[a.status] || 0);
        } else if (currentSort === 'name') {
          return a.name.localeCompare(b.name);
        } else if (currentSort === 'category') {
          return a.category.localeCompare(b.category);
        } else if (currentSort === 'status') {
          return a.status.localeCompare(b.status);
        }
        return 0;
      });

      if (currentLayout === 'grid') {
        renderGridView(filtered);
      } else {
        renderListView(filtered);
      }

      // If drawer is currently open, refresh its content in case audit changed
      if (activeDrawerToolId) {
        renderInspectorDrawer(activeDrawerToolId);
      }
    }

    let activeAuditSource = null;

    function renderToolCardInner(r) {
      const isScanning = Boolean(r.scanning);

      if (isScanning) {
        const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category || 'tool'];
        const categoriesHtml = toolCats.slice(0, 2).map(c => 
          `<span class="text-[9px] text-[#475569] uppercase tracking-wider font-mono font-medium px-1.5 py-0.5 bg-[#08090C] rounded border border-[#1F2430]">${c}</span>`
        ).join('') + (toolCats.length > 2 ? `<span class="text-[9px] text-[#475569] font-mono">+${toolCats.length - 2}</span>` : '');

        return `
          <div>
            <!-- Header: Icon, Name, Scanning Badge -->
            <div class="flex items-start justify-between gap-2.5 mb-2.5">
              <div class="flex items-center gap-2.5 min-w-0">
                <div class="w-9 h-9 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-center text-base flex-shrink-0 text-[#94A3B8]">
                  ${getToolIcon(r.id, r.category)}
                </div>
                <div class="min-w-0">
                  <h3 class="font-semibold text-[#F3F4F6] text-xs tracking-tight truncate" title="${r.name}">
                    ${r.name}
                  </h3>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <span class="relative flex h-1.5 w-1.5">
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#06B6D4] opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#06B6D4]"></span>
                    </span>
                    <span class="text-[10px] font-mono text-[#06B6D4] font-medium">Scanning...</span>
                  </div>
                </div>
              </div>
              <div class="flex-shrink-0">
                <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#06B6D41A] text-[#06B6D4] border border-[#06B6D440] whitespace-nowrap animate-pulse">
                  <i class="fa-solid fa-circle-notch fa-spin text-[9px]"></i> Scanning
                </span>
              </div>
            </div>

            <!-- Categories & Shimmer Path Skeleton -->
            <div class="space-y-2 my-2 text-xs">
              <div class="flex items-center gap-1 flex-wrap">
                ${categoriesHtml}
              </div>
              <div class="bg-[#08090C] px-2 py-1.5 rounded border border-[#1F2430] flex items-center gap-2">
                <i class="fa-solid fa-terminal text-[#475569] text-[9px]"></i>
                <div class="h-3 bg-[#141721] rounded skeleton-shimmer w-3/4"></div>
              </div>
            </div>
          </div>

          <!-- Bottom Footer Bar Skeleton -->
          <div class="pt-2 mt-1 border-t border-[#1F2430] flex items-center justify-between text-xs">
            <div class="flex items-center gap-1.5">
              <div class="h-3.5 w-14 bg-[#141721] rounded skeleton-shimmer"></div>
            </div>
            <span class="text-[10px] font-mono text-[#475569] flex items-center gap-1">
              <i class="fa-solid fa-spinner fa-spin text-[9px] text-[#06B6D4]"></i> running
            </span>
          </div>
        `;
      }

      // Completed card
      const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category];
      const categoriesHtml = toolCats.slice(0, 2).map(c => 
        `<span class="text-[9px] text-[#94A3B8] uppercase tracking-wider font-mono font-medium px-1.5 py-0.5 bg-[#08090C] rounded border border-[#1F2430]">${c}</span>`
      ).join('') + (toolCats.length > 2 ? `<span class="text-[9px] text-[#475569] font-mono">+${toolCats.length - 2}</span>` : '');

      const primaryPath = r.home_path || r.binary_path || '';
      const cleanPath = primaryPath.replace(/"/g, '&quot;');

      let companionPill = '';
      if (r.companions && r.companions.length > 0) {
        const installedComp = r.companions.filter(c => c.installed).length;
        companionPill = `
          <span class="inline-flex items-center gap-1 text-[10px] font-mono text-[#94A3B8] bg-[#08090C] px-1.5 py-0.2 rounded border border-[#1F2430]">
            <i class="fa-solid fa-layer-group text-[9px] text-[#8B5CF6]"></i> ${installedComp}/${r.companions.length}
          </span>
        `;
      }

      let diagStrip = '';
      if (r.diagnostics && r.diagnostics.length > 0) {
        diagStrip = `
          <span class="inline-flex items-center gap-1 text-[10px] font-mono font-medium text-[#F59E0B] bg-[#F59E0B1A] px-1.5 py-0.2 rounded border border-[#F59E0B40] truncate max-w-[130px]" title="${r.diagnostics[0].message}">
            <i class="fa-solid fa-triangle-exclamation text-[9px]"></i> Action
          </span>
        `;
      }

      return `
        <div>
          <!-- Header: Icon, Name, Version, Status -->
          <div class="flex items-start justify-between gap-2.5 mb-2.5">
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="w-9 h-9 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-center text-base flex-shrink-0 group-hover:border-[#2E3446] group-hover:bg-[#141721] transition">
                ${getToolIcon(r.id, r.category)}
              </div>
              <div class="min-w-0">
                <h3 class="font-semibold text-[#F3F4F6] text-xs tracking-tight truncate group-hover:text-[#10B981] transition" title="${r.name}">
                  ${r.name}
                </h3>
                <div class="text-[11px] font-mono font-medium text-[#06B6D4] mt-0.5 truncate">
                  ${r.version ? 'v' + r.version : (r.installed ? '<span class="text-[#94A3B8] font-normal">Installed</span>' : '<span class="text-[#475569] font-normal">Not detected</span>')}
                </div>
              </div>
            </div>
            <div class="flex-shrink-0">
              ${getBadge(r.status)}
            </div>
          </div>

          <!-- Categories & Primary Path -->
          <div class="space-y-1.5 my-2 text-xs">
            <div class="flex items-center gap-1 flex-wrap">
              ${categoriesHtml}
            </div>
            <div class="bg-[#08090C] px-2 py-1 rounded border border-[#1F2430] flex items-center justify-between gap-1.5 min-w-0 text-[11px] font-mono text-[#94A3B8]" title="${cleanPath}">
              <div class="truncate flex items-center gap-1.5">
                <i class="fa-solid ${r.home_path ? 'fa-folder text-[#06B6D4]' : 'fa-terminal text-[#10B981]'} text-[9px] flex-shrink-0"></i>
                <span class="truncate">${primaryPath || '<span class="text-[#475569] italic">No path registered</span>'}</span>
              </div>
              ${primaryPath ? `
                <button onclick="event.stopPropagation(); copyToClipboard('${cleanPath}', 'path')" class="p-0.5 text-[#475569] hover:text-[#F3F4F6] transition flex-shrink-0" title="Copy path">
                  <i class="fa-regular fa-copy text-[9px]"></i>
                </button>
              ` : ''}
            </div>
          </div>
        </div>

        <!-- Bottom Footer Bar -->
        <div class="pt-2 mt-1 border-t border-[#1F2430] flex items-center justify-between text-xs">
          <div class="flex items-center gap-1.5 min-w-0">
            ${companionPill}
            ${diagStrip}
          </div>
          <span class="text-[11px] font-medium text-[#10B981] group-hover:translate-x-0.5 flex items-center gap-1 flex-shrink-0 transition">
            Inspect <i class="fa-solid fa-chevron-right text-[9px]"></i>
          </span>
        </div>
      `;
    }

    function renderToolRowInner(r) {
      const cleanHome = (r.home_path || '').replace(/"/g, '&quot;');
      const cleanBin = (r.binary_path || '').replace(/"/g, '&quot;');
      const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category];
      const catsDisplay = toolCats.join(', ');

      if (r.scanning) {
        return `
          <td class="py-2.5 px-3.5 font-semibold text-[#F3F4F6] flex items-center gap-2">
            <span class="w-6 h-6 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-center text-xs flex-shrink-0 text-[#94A3B8]">${getToolIcon(r.id, r.category)}</span>
            <span class="truncate max-w-[150px]">${r.name}</span>
          </td>
          <td class="py-2.5 px-3.5 uppercase text-[10px] font-mono text-[#94A3B8]">${catsDisplay}</td>
          <td class="py-2.5 px-3.5">
            <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-[#06B6D41A] text-[#06B6D4] border border-[#06B6D440] font-mono animate-pulse">
              <i class="fa-solid fa-circle-notch fa-spin text-[9px]"></i> Scanning
            </span>
          </td>
          <td class="py-2.5 px-3.5"><div class="h-3 w-12 bg-[#141721] rounded skeleton-shimmer"></div></td>
          <td class="py-2.5 px-3.5"><div class="h-3 w-28 bg-[#141721] rounded skeleton-shimmer"></div></td>
          <td class="py-2.5 px-3.5"><div class="h-3 w-28 bg-[#141721] rounded skeleton-shimmer"></div></td>
          <td class="py-2.5 px-3.5 text-right text-[#475569]">—</td>
        `;
      }

      return `
        <td class="py-2.5 px-3.5 font-semibold text-[#F3F4F6] flex items-center gap-2">
          <span class="w-6 h-6 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-center text-xs flex-shrink-0">${getToolIcon(r.id, r.category)}</span>
          <span class="truncate max-w-[150px]">${r.name}</span>
        </td>
        <td class="py-2.5 px-3.5 uppercase text-[10px] font-mono text-[#94A3B8]">${catsDisplay}</td>
        <td class="py-2.5 px-3.5">${getBadge(r.status)}</td>
        <td class="py-2.5 px-3.5 font-mono text-[#06B6D4]">${r.version ? 'v' + r.version : '—'}</td>
        <td class="py-2.5 px-3.5 font-mono text-[#94A3B8] truncate max-w-[180px]" title="${cleanHome}">${r.home_path || '<span class="text-[#475569]">—</span>'}</td>
        <td class="py-2.5 px-3.5 font-mono text-[#10B981] truncate max-w-[180px]" title="${cleanBin}">${r.binary_path || '<span class="text-[#475569]">—</span>'}</td>
        <td class="py-2.5 px-3.5 text-right">
          <button onclick="event.stopPropagation(); openInspectorDrawer('${r.id}')" class="btn-secondary-pro px-2.5 py-1 text-[11px] font-medium">Inspect</button>
        </td>
      `;
    }

    function renderGridView(tools) {
      const grid = document.getElementById('tools-grid');
      grid.innerHTML = '';

      if (tools.length === 0) {
        grid.innerHTML = `
          <div class="col-span-full py-16 text-center text-[#94A3B8] card-pro p-8">
            <i class="fa-solid fa-filter-circle-xmark text-3xl mb-3 text-[#475569] block"></i>
            <h4 class="text-sm font-semibold text-[#F3F4F6]">No Matching Tools or Runtimes</h4>
            <p class="text-xs text-[#94A3B8] mt-1 max-w-md mx-auto">No tools match your current search query and status filter.</p>
            <div class="mt-4">
              <button onclick="resetAllFilters()" class="btn-primary-pro px-4 py-1.5 text-xs font-semibold">
                Reset Search & Filters
              </button>
            </div>
          </div>
        `;
        return;
      }

      tools.forEach(r => {
        const card = document.createElement('div');
        card.id = `tool-card-${r.id}`;
        card.className = 'card-pro p-3.5 sm:p-4 flex flex-col justify-between hover:border-[#2E3446] hover:bg-[#141721] transition cursor-pointer group';
        card.onclick = () => { if (!r.scanning) openInspectorDrawer(r.id); };
        card.innerHTML = renderToolCardInner(r);
        grid.appendChild(card);
      });
    }

    function renderListView(tools) {
      const tbody = document.getElementById('tools-list-tbody');
      tbody.innerHTML = '';

      if (tools.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-12 text-center text-[#475569] font-mono italic">No tools found matching criteria.</td></tr>`;
        return;
      }

      tools.forEach(r => {
        const tr = document.createElement('tr');
        tr.id = `tool-row-${r.id}`;
        tr.className = 'hover:bg-[#141721] transition text-[#F3F4F6] cursor-pointer';
        tr.onclick = () => { if (!r.scanning) openInspectorDrawer(r.id); };
        tr.innerHTML = renderToolRowInner(r);
        tbody.appendChild(tr);
      });
    }

    function updateSingleToolInDom(report) {
      const card = document.getElementById(`tool-card-${report.id}`);
      if (card) {
        card.innerHTML = renderToolCardInner(report);
        card.onclick = () => { if (!report.scanning) openInspectorDrawer(report.id); };
      }
      const row = document.getElementById(`tool-row-${report.id}`);
      if (row) {
        row.innerHTML = renderToolRowInner(report);
        row.onclick = () => { if (!report.scanning) openInspectorDrawer(report.id); };
      }
    }

    function updateAuditMetrics() {
      const finished = allReports.filter(r => !r.scanning);
      const total = allReports.length || 1;
      const installed = finished.filter(r => r.installed).length;
      const healthy = finished.filter(r => r.status === 'healthy').length;
      const warning = finished.filter(r => r.status === 'warning').length;
      const error = finished.filter(r => r.status === 'error').length;
      const missing = finished.filter(r => r.status === 'not_found').length;

      document.getElementById('stat-total').innerText = total;
      document.getElementById('stat-installed').innerText = installed;
      document.getElementById('stat-healthy').innerText = healthy;
      document.getElementById('stat-warning').innerText = warning;
      document.getElementById('stat-error').innerText = error;
      document.getElementById('stat-missing').innerText = missing;

      const cov = Math.round((installed / total) * 100);
      document.getElementById('stat-coverage').innerText = `${cov}% coverage`;
      document.getElementById('stat-installed-bar').style.width = `${cov}%`;
      document.getElementById('stat-healthy-bar').style.width = `${Math.round((healthy / total) * 100)}%`;
      document.getElementById('stat-warning-bar').style.width = `${Math.round((warning / total) * 100)}%`;
      document.getElementById('stat-error-bar').style.width = `${Math.round((error / total) * 100)}%`;
      document.getElementById('stat-missing-bar').style.width = `${Math.round((missing / total) * 100)}%`;
    }

    function applySystemInfo(sys) {
      if (!sys) return;
      const sideOs = document.getElementById('side-os-info');
      if (sideOs) sideOs.innerText = `${sys.os_name} ${sys.os_release} (${sys.arch})`;
      const sideHost = document.getElementById('side-host-name');
      if (sideHost) sideHost.innerText = sys.hostname || 'LOCAL';
      const sidePy = document.getElementById('side-python-version');
      if (sidePy && sys.python_version) sidePy.innerText = sys.python_version;
      const sideApp = document.getElementById('side-app-version');
      if (sideApp && sys.app_version) sideApp.innerText = `v${sys.app_version}`;

      if (sys.path_count) {
        const statusPath = document.getElementById('status-path-count');
        if (statusPath) statusPath.innerText = sys.path_count;
      }
      if (sys.ram_footprint_mb) {
        const procRam = document.getElementById('status-process-ram') || document.getElementById('status-ram-count');
        if (procRam) procRam.innerText = `${sys.ram_footprint_mb} MB`;
        const settProcRam = document.getElementById('settings-process-ram');
        if (settProcRam) settProcRam.innerText = `${sys.ram_footprint_mb} MB`;
      }
    }

    async function fetchAudit() {
      const icon = document.getElementById('rescan-icon');
      if (icon) icon.classList.add('fa-spin');

      if (activeAuditSource) {
        activeAuditSource.close();
        activeAuditSource = null;
      }

      try {
        // Step 1: Pre-populate or mark tools as scanning immediately
        if (!allReports || allReports.length === 0) {
          const toolsRes = await fetch('/api/tools');
          if (toolsRes.ok) {
            const initialTools = await toolsRes.json();
            allReports = initialTools.map(t => ({
              ...t,
              scanning: true,
              status: 'scanning',
              version: null,
              home_path: null,
              binary_path: null,
              companions: [],
              diagnostics: []
            }));
          }
        } else {
          allReports.forEach(r => { r.scanning = true; });
        }

        renderCategoryPills();
        updateStatusFilterUI();
        renderTools();
        updateAuditMetrics();

        // Step 2: Stream results asynchronously using EventSource
        if (window.EventSource) {
          await new Promise((resolve) => {
            const es = new EventSource('/api/audit/stream');
            activeAuditSource = es;

            es.onmessage = (event) => {
              try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'init') {
                  if (msg.system) applySystemInfo(msg.system);
                } else if (msg.type === 'tool') {
                  const rep = msg.report;
                  const idx = allReports.findIndex(r => r.id === rep.id);
                  if (idx !== -1) {
                    allReports[idx] = rep;
                  } else {
                    allReports.push(rep);
                  }
                  updateSingleToolInDom(rep);
                  updateAuditMetrics();
                  if (activeDrawerToolId === rep.id) {
                    renderInspectorDrawer(activeDrawerToolId);
                  }
                } else if (msg.type === 'done') {
                  allReports.forEach(r => { delete r.scanning; });
                  if (msg.system) applySystemInfo(msg.system);
                  updateAuditMetrics();
                  renderCategoryPills();
                  if (searchQuery || activeStatusFilter || activeCategory !== 'all') {
                    renderTools();
                  }
                  fetchSearchTelemetry();
                  es.close();
                  activeAuditSource = null;
                  resolve();
                }
              } catch (parseErr) {
                console.error('Error parsing SSE event', parseErr);
              }
            };

            es.onerror = async () => {
              es.close();
              activeAuditSource = null;
              // Fallback to standard fetch
              try {
                const res = await fetch('/api/audit');
                const data = await res.json();
                allReports = data.reports || [];
                if (data.system) applySystemInfo(data.system);
                renderCategoryPills();
                updateStatusFilterUI();
                renderTools();
                updateAuditMetrics();
                fetchSearchTelemetry();
              } catch (fallbackErr) {
                showToast('Error auditing environment', true);
              }
              resolve();
            };
          });
        } else {
          // Standard fetch fallback for environments without EventSource
          const res = await fetch('/api/audit');
          const data = await res.json();
          allReports = data.reports || [];
          if (data.system) applySystemInfo(data.system);
          renderCategoryPills();
          updateStatusFilterUI();
          renderTools();
          updateAuditMetrics();
          fetchSearchTelemetry();
        }
      } catch (err) {
        showToast('Error auditing environment', true);
      } finally {
        if (icon) icon.classList.remove('fa-spin');
      }
    }

    // ==================== TAB 2: PORT MANAGER ====================
    function setPortViewMode(mode) {
      currentPortView = mode;
      const flatBtn = document.getElementById('port-view-flat-btn');
      const groupedBtn = document.getElementById('port-view-grouped-btn');
      const flatContainer = document.getElementById('ports-flat-container');
      const groupedContainer = document.getElementById('ports-grouped-container');

      if (mode === 'flat') {
        flatBtn.className = 'px-2.5 py-1 rounded text-xs bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 font-semibold transition flex items-center gap-1.5';
        groupedBtn.className = 'px-2.5 py-1 rounded text-xs text-slate-400 hover:text-white border border-transparent font-medium transition flex items-center gap-1.5';
        flatContainer.classList.remove('hidden');
        groupedContainer.classList.add('hidden');
      } else {
        flatBtn.className = 'px-2.5 py-1 rounded text-xs text-slate-400 hover:text-white border border-transparent font-medium transition flex items-center gap-1.5';
        groupedBtn.className = 'px-2.5 py-1 rounded text-xs bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 font-semibold transition flex items-center gap-1.5';
        flatContainer.classList.add('hidden');
        groupedContainer.classList.remove('hidden');
      }
      renderPorts();
    }

    function getPortCategory(port) {
      const p = parseInt(port, 10);
      const webPorts = [80, 443, 3000, 3001, 3002, 4000, 4200, 4321, 5000, 5173, 5174, 8000, 8080, 8081, 8888, 9000, 9999];
      if (webPorts.includes(p)) {
        return { label: 'Web / HTTP', icon: 'fa-globe', badge: 'bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/30' };
      }
      const dbPorts = [3306, 5432, 6379, 27017, 1433, 9042, 1521, 5984, 8529];
      if (dbPorts.includes(p)) {
        return { label: 'Database', icon: 'fa-database', badge: 'bg-[#10B981]/15 text-[#10B981] border-[#10B981]/30' };
      }
      const devPorts = [9229, 5005, 5858, 2345, 9003];
      if (devPorts.includes(p)) {
        return { label: 'Dev Debug', icon: 'fa-bug', badge: 'bg-[#8B5CF6]/15 text-[#8B5CF6] border-[#8B5CF6]/30' };
      }
      return { label: 'Service', icon: 'fa-network-wired', badge: 'bg-[#141721] text-slate-400 border-[#1F2430]' };
    }

    function isWebPort(port, isDevPort) {
      const p = parseInt(port, 10);
      const webPorts = [80, 443, 3000, 3001, 3002, 4000, 4200, 4321, 5000, 5173, 5174, 8000, 8080, 8081, 8888, 9000, 9999];
      return webPorts.includes(p) || isDevPort;
    }

    async function fetchPorts(isUserClick = false) {
      const icon = document.getElementById('ports-refresh-icon');
      const btn = document.getElementById('btn-refresh-ports');
      if (icon) icon.classList.add('fa-spin');
      if (btn) btn.disabled = true;
      try {
        const devToggle = document.getElementById('ports-dev-toggle');
        const devOnly = devToggle ? devToggle.checked : false;
        const res = await fetch(`/api/ports?dev_only=${devOnly}`);
        allPorts = await res.json();

        const devCount = allPorts.filter(p => p.is_dev_port).length;
        const critCount = allPorts.filter(p => p.is_system_critical).length;
        const statTotal = document.getElementById('stat-ports-total');
        const statDev = document.getElementById('stat-ports-dev');
        const statCrit = document.getElementById('stat-ports-crit');
        if (statTotal) statTotal.innerText = allPorts.length;
        if (statDev) statDev.innerText = devCount;
        if (statCrit) statCrit.innerText = critCount;

        const sideBadge = document.getElementById('side-ports-badge');
        if (sideBadge) sideBadge.innerText = devCount > 0 ? devCount : allPorts.length;

        renderPorts();
        if (isUserClick) {
          showToast(`Sockets updated (${allPorts.length} listening)`);
        }
      } catch (err) {
        showToast('Error loading sockets', true);
      } finally {
        if (icon) icon.classList.remove('fa-spin');
        if (btn) btn.disabled = false;
      }
    }

    function renderPorts() {
      if (currentPortView === 'flat') {
        renderPortsTable();
      } else {
        renderPortsGrouped();
      }
    }

    function getFilteredPorts() {
      const query = (document.getElementById('ports-search-input')?.value || '').toLowerCase().trim();
      return allPorts.filter(p => {
        if (!query) return true;
        return (
          p.port.toString().includes(query) ||
          p.process_name.toLowerCase().includes(query) ||
          p.pid.toString().includes(query) ||
          p.address.includes(query)
        );
      });
    }

    function renderPortsTable() {
      const tbody = document.getElementById('ports-table-body');
      tbody.innerHTML = '';
      const filtered = getFilteredPorts();

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-12 text-center text-slate-500 italic font-mono text-xs">No listening sockets found matching criteria.</td></tr>`;
        return;
      }

      filtered.forEach(p => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-[#141721]/60 transition text-slate-300 border-b border-[#1F2430]/50';

        const portBadge = p.is_dev_port
          ? `<span class="inline-flex items-center gap-1 font-mono font-semibold text-[#06B6D4] bg-[#06B6D4]/10 px-2 py-0.5 rounded border border-[#06B6D4]/25">:${p.port}</span>`
          : `<span class="font-mono font-semibold text-slate-200">:${p.port}</span>`;

        const cat = getPortCategory(p.port);
        const tagBadge = `<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold font-mono border ${cat.badge}"><i class="fa-solid ${cat.icon} text-[9px]"></i> ${cat.label}</span>`;

        const statusBadge = p.is_system_critical
          ? `<span class="text-rose-400 font-medium inline-flex items-center gap-1.5 text-xs"><i class="fa-solid fa-shield-halved text-[10px]"></i> Protected OS</span>`
          : `<span class="text-[#10B981] font-medium inline-flex items-center gap-1.5 text-xs"><i class="fa-solid fa-user text-[10px]"></i> User Process</span>`;

        const browserBtn = isWebPort(p.port, p.is_dev_port)
          ? `<a href="http://localhost:${p.port}" target="_blank" class="btn-secondary-pro text-[11px] py-1 px-2.5 inline-flex items-center gap-1" title="Open in browser"><i class="fa-solid fa-arrow-up-right-from-square text-[9px] text-[#10B981]"></i> Open</a>`
          : '';

        const actionBtn = p.is_system_critical
          ? `<button onclick="openKillModal(${p.port}, '${p.process_name}', ${p.pid}, true)" class="px-2.5 py-1 bg-[#141721] hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 rounded text-[11px] font-medium transition border border-[#1F2430]">Protected</button>`
          : `<button onclick="openKillModal(${p.port}, '${p.process_name}', ${p.pid}, false)" class="btn-destructive text-[11px] py-1 px-2.5">Kill</button>`;

        tr.innerHTML = `
          <td class="py-3 px-4 font-mono">${portBadge}</td>
          <td class="py-3 px-4">${tagBadge}</td>
          <td class="py-3 px-4 font-semibold text-white truncate max-w-[180px]" title="${p.process_name}">${p.process_name}</td>
          <td class="py-3 px-4 font-mono text-amber-400">${p.pid}</td>
          <td class="py-3 px-4 font-mono text-slate-400">${p.address}</td>
          <td class="py-3 px-4">${statusBadge}</td>
          <td class="py-3 px-4 text-right">
            <div class="flex items-center justify-end gap-1.5">
              ${browserBtn}
              ${actionBtn}
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function renderPortsGrouped() {
      const container = document.getElementById('ports-grouped-container');
      container.innerHTML = '';
      const filtered = getFilteredPorts();

      if (filtered.length === 0) {
        container.innerHTML = `<div class="card-pro p-12 text-center text-slate-500 italic font-mono text-xs">No listening sockets found matching criteria.</div>`;
        return;
      }

      // Group by process_name + PID
      const groups = {};
      filtered.forEach(p => {
        const key = `${p.process_name} (PID ${p.pid})`;
        if (!groups[key]) {
          groups[key] = {
            process_name: p.process_name,
            pid: p.pid,
            is_system_critical: p.is_system_critical,
            sockets: []
          };
        }
        groups[key].sockets.push(p);
      });

      Object.values(groups).forEach(g => {
        const card = document.createElement('div');
        card.className = 'card-pro p-4 sm:p-5 space-y-3.5';

        const killBtn = g.is_system_critical
          ? `<button onclick="openKillModal(${g.sockets[0].port}, '${g.process_name}', ${g.pid}, true)" class="px-2.5 py-1 bg-[#141721] hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 rounded text-[11px] font-medium transition border border-[#1F2430]">Protected</button>`
          : `<button onclick="openKillModal(${g.sockets[0].port}, '${g.process_name}', ${g.pid}, false)" class="btn-destructive text-[11px] py-1 px-2.5">Kill Process</button>`;

        const socketsHtml = g.sockets.map(p => {
          const cat = getPortCategory(p.port);
          const browserLink = isWebPort(p.port, p.is_dev_port)
            ? `<a href="http://localhost:${p.port}" target="_blank" class="text-[10px] text-[#10B981] hover:underline font-mono font-semibold flex items-center gap-1 ml-1"><i class="fa-solid fa-arrow-up-right-from-square text-[9px]"></i> Open</a>`
            : '';

          return `
            <div class="bg-[#08090C] p-2.5 rounded border border-[#1F2430] flex items-center justify-between gap-2 text-xs">
              <div class="flex items-center gap-2 min-w-0">
                <span class="font-mono font-semibold ${p.is_dev_port ? 'text-[#06B6D4]' : 'text-slate-200'}">:${p.port}</span>
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold font-mono border ${cat.badge}">${cat.label}</span>
                <span class="font-mono text-[10px] text-slate-500 truncate">${p.address}</span>
              </div>
              <div class="flex items-center gap-2 flex-shrink-0">
                ${browserLink}
              </div>
            </div>
          `;
        }).join('');

        card.innerHTML = `
          <div class="flex items-center justify-between gap-3 border-b border-[#1F2430] pb-3">
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="w-8 h-8 rounded bg-[#141721] border border-[#1F2430] flex items-center justify-center text-xs font-bold text-[#10B981] flex-shrink-0">
                <i class="fa-solid fa-microchip"></i>
              </div>
              <div class="min-w-0">
                <div class="font-semibold text-white text-sm truncate">${g.process_name}</div>
                <div class="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                  <span>PID: <strong class="text-amber-400">${g.pid}</strong></span>
                  <span>•</span>
                  <span>${g.sockets.length} listening socket(s)</span>
                </div>
              </div>
            </div>
            <div>${killBtn}</div>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            ${socketsHtml}
          </div>
        `;
        container.appendChild(card);
      });
    }

    function openKillModal(port, processName, pid, isCritical) {
      pendingKill = { port, isCritical };
      document.getElementById('modal-kill-port').innerText = `:${port}`;
      document.getElementById('modal-kill-name').innerText = processName;
      document.getElementById('modal-kill-pid').innerText = pid;

      const warningEl = document.getElementById('modal-kill-warning');
      const forceBox = document.getElementById('modal-force-checkbox');
      forceBox.checked = false;

      if (isCritical) warningEl.classList.remove('hidden');
      else warningEl.classList.add('hidden');

      document.getElementById('kill-modal').classList.remove('hidden');
    }

    function closeKillModal() {
      document.getElementById('kill-modal').classList.add('hidden');
      pendingKill = null;
    }

    async function submitKillPort() {
      if (!pendingKill) return;
      const force = document.getElementById('modal-force-checkbox').checked;

      try {
        const res = await fetch('/api/ports/kill', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ port: pendingKill.port, force })
        });
        const data = await res.json();
        closeKillModal();

        if (data.success) {
          showToast(data.message);
          await fetchPorts();
        } else {
          showToast(data.message, true);
        }
      } catch (err) {
        showToast('Error killing process', true);
      }
    }

    // ==================== TAB 3: PROJECT AUDITOR ====================
    function getRecentProjects() {
      try {
        const list = JSON.parse(localStorage.getItem('devtoolkit_recent_projects') || '[]');
        return Array.isArray(list) ? list : [];
      } catch (e) {
        return [];
      }
    }

    function addRecentProject(path) {
      if (!path || path === '.') return;
      try {
        let list = getRecentProjects().filter(p => p !== path);
        list.unshift(path);
        if (list.length > 4) list = list.slice(0, 4);
        localStorage.setItem('devtoolkit_recent_projects', JSON.stringify(list));
        renderRecentProjects();
      } catch (e) {}
    }

    function clearRecentProjects() {
      try {
        localStorage.removeItem('devtoolkit_recent_projects');
        renderRecentProjects();
        showToast('Cleared recent projects history');
      } catch (e) {}
    }

    function renderRecentProjects() {
      const container = document.getElementById('project-recent-chips');
      if (!container) return;
      const recents = getRecentProjects();
      if (recents.length === 0) {
        container.innerHTML = '';
        return;
      }
      container.innerHTML = recents.map(p => {
        const cleanP = p.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `
          <button onclick="setAndAuditProject('${cleanP}')" class="px-2 py-0.5 rounded bg-[#141721] hover:bg-[#141721]/80 hover:border-[#10B981]/50 text-slate-300 font-mono text-[11px] truncate max-w-[180px] transition border border-[#1F2430]" title="${p}">
            ${p}
          </button>
        `;
      }).join('') + `
        <button onclick="clearRecentProjects()" class="text-slate-500 hover:text-rose-400 p-1 transition" title="Clear recent paths">
          <i class="fa-regular fa-trash-can text-[10px]"></i>
        </button>
      `;
    }

    function setAndAuditProject(val) {
      document.getElementById('project-path-input').value = val;
      runProjectAudit();
    }

    async function browseProjectFolder() {
      const btn = document.getElementById('btn-browse-project');
      const icon = document.getElementById('browse-folder-icon');
      const input = document.getElementById('project-path-input');
      const originalIcon = icon ? icon.className : 'fa-regular fa-folder-open text-[#10B981] text-xs';

      try {
        if (icon) icon.className = 'fa-solid fa-spinner fa-spin text-[#10B981] text-xs';
        if (btn) btn.disabled = true;

        const currentVal = input ? input.value.trim() : '';
        const res = await fetch('/api/action/select-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ initial_path: currentVal || '.' })
        });

        if (res.ok) {
          const data = await res.json();
          if (data.status === 'ok' && data.path) {
            input.value = data.path;
            showToast(`Selected: ${data.path}`);
            runProjectAudit();
          }
        }
      } catch (err) {
        console.error('Failed to select folder:', err);
      } finally {
        if (icon) icon.className = originalIcon;
        if (btn) btn.disabled = false;
      }
    }

    function copyAllProjectActions() {
      if (!currentProjectActions || currentProjectActions.length === 0) {
        showToast('No actions available to copy');
        return;
      }
      const scriptText = currentProjectActions.join('\n');
      copyToClipboard(scriptText, 'all setup commands');
    }

    async function runProjectAudit() {
      const input = document.getElementById('project-path-input');
      const pathVal = input.value.trim() || '.';
      const btn = document.getElementById('btn-audit-project');
      const icon = document.getElementById('audit-project-icon');
      const resultsContainer = document.getElementById('project-results-container');

      icon.className = 'fa-solid fa-spinner fa-spin';
      btn.disabled = true;

      try {
        const res = await fetch('/api/project/audit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: pathVal })
        });
        if (!res.ok) {
          const err = await res.json();
          showToast(err.detail || 'Directory not found', true);
          return;
        }

        const data = await res.json();
        addRecentProject(data.project_path);
        resultsContainer.classList.remove('hidden');

        document.getElementById('rep-project-name').innerText = data.project_name;
        document.getElementById('rep-project-path').innerText = data.project_path;

        const typesContainer = document.getElementById('rep-detected-types');
        typesContainer.innerHTML = (data.detected_types || []).map(t =>
          `<span class="px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 uppercase tracking-wider">${t}</span>`
        ).join('');

        // Readiness Score Calculation & Scorecard
        const totalChecks = (data.checks || []).length;
        const satisfiedChecks = (data.checks || []).filter(c => c.satisfied).length;
        const missingChecks = totalChecks - satisfiedChecks;
        const scorePct = totalChecks > 0 ? Math.round((satisfiedChecks / totalChecks) * 100) : 100;

        const scorePctEl = document.getElementById('rep-score-pct');
        const scoreBarEl = document.getElementById('rep-score-bar');
        scorePctEl.innerText = `${scorePct}%`;
        scoreBarEl.style.width = `${scorePct}%`;

        if (scorePct === 100) {
          scorePctEl.className = 'text-2xl font-bold font-mono text-[#10B981]';
          scoreBarEl.className = 'h-full bg-[#10B981] rounded transition-all duration-500';
        } else if (scorePct >= 60) {
          scorePctEl.className = 'text-2xl font-bold font-mono text-amber-400';
          scoreBarEl.className = 'h-full bg-amber-400 rounded transition-all duration-500';
        } else {
          scorePctEl.className = 'text-2xl font-bold font-mono text-rose-400';
          scoreBarEl.className = 'h-full bg-rose-500 rounded transition-all duration-500';
        }

        document.getElementById('rep-satisfied-count').innerText = `${satisfiedChecks} satisfied`;
        document.getElementById('rep-missing-count').innerText = `${missingChecks} missing`;

        const badgeEl = document.getElementById('rep-status-badge');
        if (data.ready_to_build) {
          badgeEl.innerHTML = '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold font-mono bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30"><i class="fa-solid fa-check text-[11px]"></i> READY TO BUILD</span>';
        } else {
          badgeEl.innerHTML = '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold font-mono bg-rose-500/15 text-rose-400 border border-rose-500/30"><i class="fa-solid fa-triangle-exclamation text-[11px]"></i> PREREQS MISSING</span>';
        }

        const tbody = document.getElementById('project-checks-tbody');
        tbody.innerHTML = '';
        (data.checks || []).forEach(c => {
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-[#141721]/60 text-slate-300 border-b border-[#1F2430]/50';
          const stat = c.satisfied
            ? '<span class="text-[#10B981] font-semibold inline-flex items-center gap-1 font-mono text-xs"><i class="fa-solid fa-check text-[10px]"></i> Satisfied</span>'
            : '<span class="text-rose-400 font-semibold inline-flex items-center gap-1 font-mono text-xs"><i class="fa-solid fa-xmark text-[10px]"></i> Missing</span>';
          tr.innerHTML = `
            <td class="py-2.5 px-4">${stat}</td>
            <td class="py-2.5 px-4 font-semibold text-white">${c.name}</td>
            <td class="py-2.5 px-4 font-mono text-slate-400 text-xs">${c.required}</td>
            <td class="py-2.5 px-4 font-mono text-[#06B6D4] text-xs">${c.detected || '<span class="text-slate-500">None</span>'}</td>
            <td class="py-2.5 px-4 text-slate-300 text-xs">${c.message}</td>
          `;
          tbody.appendChild(tr);
        });

        // Recommended actions
        currentProjectActions = data.suggested_actions || [];
        const actionsCard = document.getElementById('project-actions-card');
        const actionsList = document.getElementById('project-actions-list');
        if (currentProjectActions.length > 0) {
          actionsCard.classList.remove('hidden');
          actionsList.innerHTML = currentProjectActions.map(act => {
            const cleanCmd = act.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
            return `
              <div class="flex items-center justify-between p-2.5 rounded bg-[#08090C] border border-[#1F2430] text-xs">
                <div class="font-mono text-slate-200 truncate mr-2"><code>${act}</code></div>
                <button onclick="copyToClipboard('${cleanCmd}', 'command')" class="btn-secondary-pro text-[11px] py-1 px-2.5 font-mono flex-shrink-0">Copy</button>
              </div>
            `;
          }).join('');
        } else {
          actionsCard.classList.add('hidden');
        }
      } catch (err) {
        showToast('Error auditing project', true);
      } finally {
        icon.className = 'fa-solid fa-wand-magic-sparkles';
        btn.disabled = false;
      }
    }

    // ==================== TAB 4: SETTINGS & SEARCH ROOTS ====================
    function fillSettingsPath(p) {
      document.getElementById('settings-path-input').value = p;
    }

    async function loadConfig() {
      try {
        const res = await fetch('/api/config');
        currentConfig = await res.json();
        renderSettingsList();
      } catch (e) {
        console.error('Error loading config:', e);
      }
    }

    function renderSettingsList() {
      const listEl = document.getElementById('settings-paths-list');
      const bannerEl = document.getElementById('search-paths-banner');
      const bannerListEl = document.getElementById('banner-paths-list');

      const paths = currentConfig.search_paths || [];
      const fsBannerListEl = document.getElementById('fs-banner-paths-list');
      if (fsBannerListEl) {
        fsBannerListEl.innerText = paths.length > 0 ? paths.join(', ') : 'None configured (Add directories in Settings)';
      }

      if (paths.length === 0) {
        listEl.innerHTML = '<div class="text-xs text-slate-500 italic p-3 bg-[#08090C] rounded border border-[#1F2430] text-center font-mono">No custom search roots configured. Standard OS & ecosystem discovery is active.</div>';
        bannerEl.classList.add('hidden');
        return;
      }

      bannerEl.classList.remove('hidden');
      bannerListEl.innerText = paths.join(', ');

      listEl.innerHTML = paths.map((p, idx) => `
        <div class="flex items-center justify-between p-2.5 bg-[#08090C] rounded border border-[#1F2430] text-xs">
          <div class="flex items-center gap-2 font-mono text-slate-200 truncate" title="${escapeHtml(p)}">
            <i class="fa-regular fa-folder text-[#10B981]"></i>
            <span class="truncate">${escapeHtml(p)}</span>
          </div>
          <button onclick="removeSearchPathByIndex(${idx})" class="p-1 hover:text-rose-400 text-slate-500 transition" title="Remove path">
            <i class="fa-solid fa-trash-can text-xs"></i>
          </button>
        </div>
      `).join('');
    }

    async function submitSearchPath() {
      const input = document.getElementById('settings-path-input');
      const path = input.value.trim();
      if (!path) return;

      try {
        const res = await fetch('/api/config/search-paths', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path })
        });
        if (res.ok) {
          input.value = '';
          showToast('Search path added! Refreshing...');
          await loadConfig();
          await fetchAudit();
        } else {
          const err = await res.json();
          showToast(err.detail || 'Directory does not exist', true);
        }
      } catch (e) {
        showToast('Error adding search path', true);
      }
    }

    async function removeSearchPathByIndex(idx) {
      const paths = currentConfig.search_paths || [];
      const path = paths[idx];
      await removeSearchPath(path, idx);
    }

    async function removeSearchPath(path, idx) {
      try {
        const payload = {};
        if (typeof idx === 'number') payload.index = idx;
        if (path) payload.path = path;

        const res = await fetch('/api/config/search-paths', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.removed) {
            showToast('Search path removed');
          } else {
            showToast('Path was not found in config', true);
          }
          await loadConfig();
          await fetchAudit();
        } else {
          showToast('Error removing path', true);
        }
      } catch (e) {
        showToast('Error removing path', true);
      }
    }

    async function browseSettingsFolder() {
      const input = document.getElementById('settings-path-input');
      try {
        const currentVal = input ? input.value.trim() : '';
        const res = await fetch('/api/action/select-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ initial_path: currentVal || '' })
        });

        if (res.ok) {
          const data = await res.json();
          if (data.status === 'ok' && data.path) {
            input.value = data.path;
          }
        }
      } catch (err) {
        console.error('Failed to select settings folder:', err);
      }
    }

    let latestSearchTelemetry = null;

    async function fetchSearchTelemetry() {
      try {
        const res = await fetch('/api/search/status');
        if (!res.ok) return;
        const data = await res.json();
        updateSearchTelemetryUI(data);
      } catch (err) {
        console.error('Failed to fetch search telemetry:', err);
      }
    }

    function updateSearchTelemetryUI(data) {
      if (!data) return;
      latestSearchTelemetry = data;

      const isIndexing = Boolean(data.is_indexing || data.status === 'indexing');
      const isReady = Boolean(data.status === 'ready');
      const filesCount = data.total_files >= 1000 ? `${(data.total_files / 1000).toFixed(1)}k` : (data.total_files || 0);
      const shortCount = data.total_files >= 1000 ? `${(data.total_files / 1000).toFixed(0)}k` : (data.total_files || 0);

      // 1. Sidebar Navigation Button Badge (Fast Search)
      const sideNavBadge = document.getElementById('side-search-count-badge');
      if (sideNavBadge) {
        if (isIndexing) {
          sideNavBadge.innerText = 'Indexing...';
          sideNavBadge.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#F59E0B1A] text-[#F59E0B] border border-[#F59E0B40] flex-shrink-0';
        } else if (isReady) {
          sideNavBadge.innerText = `${shortCount}`;
          sideNavBadge.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#10B9811A] text-[#10B981] border border-[#10B98140] flex-shrink-0';
        } else {
          sideNavBadge.innerText = 'Idle';
          sideNavBadge.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#141721] text-[#94A3B8] border border-[#1F2430] flex-shrink-0';
        }
      }

      // 2. Sidebar Footer indicator
      const sideStatus = document.getElementById('side-search-status');
      const sideIcon = document.getElementById('side-search-icon');
      if (sideStatus) {
        if (isIndexing) {
          sideStatus.innerText = 'Indexing...';
          sideStatus.className = 'text-[#F59E0B] font-mono truncate max-w-[120px]';
          if (sideIcon) sideIcon.className = 'fa-solid fa-arrows-rotate fa-spin text-[#F59E0B] text-[10px]';
        } else if (isReady) {
          const readyText = data.is_live ? 'Ready (live)' : `Ready (${filesCount})`;
          sideStatus.innerText = readyText;
          sideStatus.className = 'text-[#10B981] font-mono truncate max-w-[120px]';
          sideStatus.title = `${(data.total_files || 0).toLocaleString()} files indexed in ${data.duration_ms}ms (${data.search_memory_formatted || '0 B'})${data.is_live ? ' • Real-time live updating active' : ''}`;
          if (sideIcon) sideIcon.className = 'fa-solid fa-bolt text-[#10B981] text-[10px]';
        } else {
          sideStatus.innerText = 'Idle';
          sideStatus.className = 'text-[#94A3B8] font-mono truncate max-w-[120px]';
          if (sideIcon) sideIcon.className = 'fa-solid fa-bolt text-[#475569] text-[10px]';
        }
      }

      // 3. Fast Search Total Indexed Metrics Badge
      const fsTotalBadge = document.getElementById('fs-index-total-badge');
      if (fsTotalBadge) {
        const memStr = data.search_memory_formatted ? ` (${data.search_memory_formatted})` : '';
        const liveTag = data.is_live ? ' • Live' : '';
        fsTotalBadge.innerText = `${(data.total_files || 0).toLocaleString()} files indexed${memStr}${liveTag}`;
        if (data.is_live) {
          fsTotalBadge.className = 'font-mono text-[11px] text-[#10B981]';
        } else {
          fsTotalBadge.className = 'font-mono text-[11px] text-[#475569]';
        }
      }

      // 4. Fast Search Monitored Paths Banner
      const fsBannerList = document.getElementById('fs-banner-paths-list');
      if (fsBannerList) {
        const roots = (data.roots_scanned && data.roots_scanned.length > 0)
          ? data.roots_scanned
          : ((currentConfig && currentConfig.search_paths && currentConfig.search_paths.length > 0)
              ? currentConfig.search_paths
              : []);
        if (roots.length > 0) {
          fsBannerList.innerText = roots.join(', ');
          fsBannerList.title = roots.join('\n');
        } else {
          fsBannerList.innerText = 'None configured (Add directories in Settings)';
          fsBannerList.title = 'No custom search roots configured. Click Manage Paths to configure.';
        }
      }

      // 5. Persistent Bottom Status Bar
      const statusSearchRam = document.getElementById('status-search-ram');
      if (statusSearchRam && data.search_memory_formatted) {
        statusSearchRam.innerText = data.search_memory_formatted;
      }
      const statusProcRam = document.getElementById('status-process-ram');
      if (statusProcRam && data.process_ram_formatted) {
        statusProcRam.innerText = data.process_ram_formatted;
      }

      // 6. Settings Tab Search Telemetry Card
      const badge = document.getElementById('settings-search-badge');
      if (badge) {
        if (isIndexing) {
          badge.className = 'px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#F59E0B1A] text-[#F59E0B] border border-[#F59E0B40]';
          badge.innerText = 'Indexing...';
        } else if (isReady) {
          badge.className = 'px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#10B9811A] text-[#10B981] border border-[#10B98140]';
          badge.innerText = data.is_live ? 'Ready (live)' : 'Ready';
        } else {
          badge.className = 'px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#141721] text-[#94A3B8] border border-[#1F2430]';
          badge.innerText = 'Idle';
        }
      }

      // Settings Real-Time Toggle & Badge
      const rtToggle = document.getElementById('settings-toggle-realtime');
      if (rtToggle && data.realtime_enabled !== undefined) {
        rtToggle.checked = Boolean(data.realtime_enabled);
      }
      const rtBadge = document.getElementById('settings-realtime-badge');
      if (rtBadge) {
        if (data.is_live) {
          rtBadge.innerText = 'Active (Live)';
          rtBadge.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#10B9811A] text-[#10B981] border border-[#10B98140]';
        } else if (data.realtime_enabled) {
          rtBadge.innerText = 'Enabled';
          rtBadge.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#3B82F61A] text-[#3B82F6] border border-[#3B82F640]';
        } else {
          rtBadge.innerText = 'Disabled';
          rtBadge.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#141721] text-[#94A3B8] border border-[#1F2430]';
        }
      }

      const stratEl = document.getElementById('settings-search-strategy');
      if (stratEl) stratEl.innerText = data.engine_used || 'None';

      const filesEl = document.getElementById('settings-search-files');
      if (filesEl) filesEl.innerText = (data.total_files || 0).toLocaleString();

      const dirsEl = document.getElementById('settings-search-dirs');
      if (dirsEl) dirsEl.innerText = (data.total_dirs || 0).toLocaleString();

      const durEl = document.getElementById('settings-search-duration');
      if (durEl) durEl.innerText = `${data.duration_ms || 0.0} ms`;

      const memEl = document.getElementById('settings-search-mem');
      if (memEl) memEl.innerText = data.search_memory_formatted || '0 B';

      const procRamEl = document.getElementById('settings-process-ram');
      if (procRamEl && data.process_ram_formatted) procRamEl.innerText = data.process_ram_formatted;

      const rootsEl = document.getElementById('settings-search-roots-tags');
      if (rootsEl) {
        if (data.roots_scanned && data.roots_scanned.length > 0) {
          rootsEl.innerText = data.roots_scanned.join(', ');
          rootsEl.title = data.roots_scanned.join('\n');
        } else {
          rootsEl.innerText = 'None';
        }
      }

      const lastTimeEl = document.getElementById('settings-search-last-time');
      if (lastTimeEl) {
        if (data.last_indexed_at) {
          try {
            const dt = new Date(data.last_indexed_at);
            lastTimeEl.innerText = dt.toLocaleTimeString();
          } catch {
            lastTimeEl.innerText = data.last_indexed_at;
          }
        } else {
          lastTimeEl.innerText = 'Never';
        }
      }
    }

    async function triggerManualReindex() {
      const spinner = document.getElementById('reindex-spinner');
      const btnText = document.getElementById('reindex-btn-text');
      const btn = document.getElementById('btn-reindex-search');

      if (spinner) spinner.classList.add('fa-spin');
      if (btnText) btnText.innerText = 'Indexing...';
      if (btn) btn.disabled = true;

      const sideStatus = document.getElementById('side-search-status');
      if (sideStatus) sideStatus.innerText = 'Indexing...';
      const sideNavBadge = document.getElementById('side-search-count-badge');
      if (sideNavBadge) {
        sideNavBadge.innerText = 'Indexing...';
        sideNavBadge.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#F59E0B1A] text-[#F59E0B] border border-[#F59E0B40] flex-shrink-0';
      }
      const sideIcon = document.getElementById('side-search-icon');
      if (sideIcon) sideIcon.className = 'fa-solid fa-arrows-rotate fa-spin text-[#F59E0B] text-[10px]';

      try {
        const res = await fetch('/api/search/reindex', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Server returned ${res.status}`);
        }
        const data = await res.json();
        updateSearchTelemetryUI(data);
        showToast(`Search Index updated: ${(data.total_files || 0).toLocaleString()} files in ${data.duration_ms}ms`);
      } catch (err) {
        console.error('Re-indexing error:', err);
        showToast(`Error rebuilding search index: ${err.message || 'Unknown error'}`, true);
      } finally {
        if (spinner) spinner.classList.remove('fa-spin');
        if (btnText) btnText.innerText = 'Re-index Now';
        if (btn) btn.disabled = false;
      }
    }

    async function toggleRealtimeSearchSetting(enabled) {
      const toggle = document.getElementById('settings-toggle-realtime');
      const badge = document.getElementById('settings-realtime-badge');
      if (toggle) toggle.disabled = true;
      if (badge && enabled) {
        badge.innerText = 'Syncing...';
        badge.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#F59E0B1A] text-[#F59E0B] border border-[#F59E0B40]';
      }

      try {
        const res = await fetch('/api/search/realtime', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: Boolean(enabled) })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Server returned ${res.status}`);
        }
        const data = await res.json();
        updateSearchTelemetryUI(data);
        showToast(enabled ? `Real-time updates enabled (${(data.total_files || 0).toLocaleString()} files synchronized)` : 'Real-time updates disabled');
        if (currentActiveTab === 'search') {
          triggerSearch();
        }
      } catch (err) {
        console.error('Failed to toggle realtime search:', err);
        showToast(`Error updating real-time setting: ${err.message || 'Unknown error'}`, true);
        if (toggle) toggle.checked = !enabled;
      } finally {
        if (toggle) toggle.disabled = false;
      }
    }

    // ==================== FAST SEARCH (EVERYTHING ENGINE) ====================
    let fsQuery = '';
    let fsModifiers = { case: false, word: false, path: false, regex: false };
    let fsCategory = 'all';
    let fsScope = 'all';
    let fsSizeFilter = 'any';
    let fsDateFilter = 'any';
    let fsQuickExt = '';
    let fsSortBy = 'relevance';
    let fsSortDesc = false;
    let fsLimit = 100;
    let fsOffset = 0;
    let fsCurrentResults = [];
    let fsTotalMatches = 0;
    let fsSelectedRowIndex = -1;
    let fsDebounceTimer = null;
    let fsIsInitialized = false;

    function initSearchTab() {
      if (!fsIsInitialized) {
        fsIsInitialized = true;
        const input = document.getElementById('fs-search-input');
        if (input) {
          input.addEventListener('input', (e) => {
            fsQuery = e.target.value;
            const clearBtn = document.getElementById('fs-clear-btn');
            if (clearBtn) {
              if (fsQuery.length > 0) clearBtn.classList.remove('hidden');
              else clearBtn.classList.add('hidden');
            }
            syncVisualFiltersFromQuery();
            if (fsDebounceTimer) clearTimeout(fsDebounceTimer);
            fsDebounceTimer = setTimeout(() => triggerSearch(true), 120);
          });
          input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
              clearSearchInput();
            } else if (e.key === 'ArrowDown') {
              e.preventDefault();
              navigateSearchRows(1);
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              navigateSearchRows(-1);
            } else if (e.key === 'Enter') {
              e.preventDefault();
              openSelectedSearchResult();
            }
          });
        }
      }
      triggerSearch(false);
      setTimeout(() => {
        const input = document.getElementById('fs-search-input');
        if (input) input.focus();
      }, 50);
    }

    async function triggerSearch(resetOffset = true) {
      if (resetOffset) fsOffset = 0;
      fsSelectedRowIndex = -1;

      // Query input is single source of truth for Everything syntax; category pill handles workstation type
      const payload = {
        query: fsQuery,
        case_sensitive: fsModifiers.case,
        whole_word: fsModifiers.word,
        match_path: fsModifiers.path,
        is_regex: fsModifiers.regex,
        category: fsCategory,
        scope: "all",
        size_filter: "any",
        date_filter: "any",
        ext_filter: "",
        sort_by: fsSortBy,
        sort_desc: fsSortDesc,
        limit: fsLimit,
        offset: fsOffset
      };

      try {
        const res = await fetch('/api/search/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderSearchResults(data);
      } catch (err) {
        console.error('Fast Search error:', err);
      }
    }

    function renderSearchResults(data) {
      fsCurrentResults = data.results || [];
      fsTotalMatches = data.total_matches || 0;

      // Update matching items counter
      const countEl = document.getElementById('fs-results-count');
      if (countEl) countEl.innerText = `${fsTotalMatches.toLocaleString()} matching items`;

      const durationEl = document.getElementById('fs-results-duration');
      if (durationEl) durationEl.innerText = `${data.duration_ms || 0} ms`;

      // Update total indexed files in search metrics bar
      const totalIndexed = data.total_indexed || (latestSearchTelemetry ? latestSearchTelemetry.total_files : 0);
      const indexBadge = document.getElementById('fs-index-total-badge');
      if (indexBadge && totalIndexed > 0) {
        const memStr = latestSearchTelemetry?.search_memory_formatted ? ` (${latestSearchTelemetry.search_memory_formatted})` : '';
        indexBadge.innerText = `${totalIndexed.toLocaleString()} files indexed${memStr}`;
      }

      // NOTE: We do not overwrite side-search-count-badge here with query matches, preserving global engine status!

      // Update pagination info
      const totalPages = Math.max(1, Math.ceil(fsTotalMatches / fsLimit));
      const currentPage = Math.floor(fsOffset / fsLimit) + 1;
      const pageInfo = document.getElementById('fs-page-info');
      if (pageInfo) {
        if (fsTotalMatches === 0) {
          pageInfo.innerText = 'Page 0 of 0';
        } else {
          const startNum = fsOffset + 1;
          const endNum = Math.min(fsOffset + fsCurrentResults.length, fsTotalMatches);
          pageInfo.innerText = `Page ${currentPage} of ${totalPages} (${startNum}–${endNum})`;
        }
      }

      const prevBtn = document.getElementById('fs-prev-btn');
      const nextBtn = document.getElementById('fs-next-btn');
      if (prevBtn) prevBtn.disabled = (fsOffset <= 0);
      if (nextBtn) nextBtn.disabled = (fsOffset + fsLimit >= fsTotalMatches);

      // Render table rows
      const tbody = document.getElementById('fs-results-tbody');
      if (!tbody) return;

      if (fsCurrentResults.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="py-12 text-center text-[#475569]">
              <i class="fa-solid fa-magnifying-glass text-2xl mb-2 block opacity-40"></i>
              <div class="text-sm font-medium text-[#94A3B8]">No files or folders matched your query</div>
              <div class="text-xs text-[#475569] mt-1">Try broadening your search term or resetting active filters</div>
            </td>
          </tr>
        `;
        return;
      }

      let html = '';
      fsCurrentResults.forEach((item, idx) => {
        const icon = getFileIcon(item.name, item.is_dir);
        const escapedPath = escapeHtml(item.path);
        const escapedName = escapeHtml(item.name);
        const escapedFolder = escapeHtml(item.folder);

        html += `
          <tr id="fs-row-${idx}" class="fs-row hover:bg-[#141721] transition group border-b border-[#141721]" onclick="selectSearchRow(${idx})" ondblclick="openSearchResult('${encodeURIComponent(item.path)}')">
            <td class="py-2 px-3 font-mono text-xs text-[#F3F4F6] truncate max-w-xs" title="${escapedName}">
              <div class="flex items-center gap-2 truncate">
                <span class="flex-shrink-0 w-4 text-center">${icon}</span>
                <span class="truncate font-medium">${escapedName}</span>
              </div>
            </td>
            <td class="py-2 px-3 font-mono text-[11px] text-[#94A3B8] truncate max-w-sm" title="${escapedPath}">
              <span class="truncate cursor-pointer hover:text-[#3B82F6] hover:underline" onclick="revealSearchResult('${encodeURIComponent(item.path)}'); event.stopPropagation();">${escapedFolder}</span>
            </td>
            <td class="py-2 px-3 font-mono text-xs text-right text-[#94A3B8] flex-shrink-0 whitespace-nowrap">
              ${item.size_formatted}
            </td>
            <td class="py-2 px-3 font-mono text-[11px] text-[#475569] whitespace-nowrap">
              ${item.mtime_formatted}
            </td>
            <td class="py-2 px-3 font-mono text-[11px] text-[#94A3B8] whitespace-nowrap">
              <span class="px-1.5 py-0.5 rounded bg-[#141721] text-[#94A3B8] border border-[#1F2430] text-[10px]">${item.ext || '—'}</span>
            </td>
            <td class="py-2 px-3 text-right whitespace-nowrap">
              <div class="flex items-center justify-end gap-1.5 opacity-60 group-hover:opacity-100 transition">
                <button onclick="openSearchResult('${encodeURIComponent(item.path)}'); event.stopPropagation();" class="p-1 rounded text-[#94A3B8] hover:text-[#10B981] hover:bg-[#141721] transition cursor-pointer" title="Open File (Double-click)">
                  <i class="fa-solid fa-arrow-up-right-from-square text-[11px]"></i>
                </button>
                <button onclick="revealSearchResult('${encodeURIComponent(item.path)}'); event.stopPropagation();" class="p-1 rounded text-[#94A3B8] hover:text-[#06B6D4] hover:bg-[#141721] transition cursor-pointer" title="Reveal in Explorer">
                  <i class="fa-regular fa-folder-open text-[11px]"></i>
                </button>
                <button onclick="copySearchResultPath('${encodeURIComponent(item.path)}'); event.stopPropagation();" class="p-1 rounded text-[#94A3B8] hover:text-white hover:bg-[#141721] transition cursor-pointer" title="Copy Full Path">
                  <i class="fa-regular fa-copy text-[11px]"></i>
                </button>
              </div>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = html;
    }

    function getFileIcon(filename, isDir) {
      if (isDir) return '<i class="fa-solid fa-folder text-[#F59E0B]"></i>';
      const parts = filename.toLowerCase().split('.');
      const ext = parts.length > 1 ? parts.pop() : '';
      if (['py', 'pyw'].includes(ext)) return '<i class="fa-brands fa-python text-[#3B82F6]"></i>';
      if (['js', 'mjs', 'cjs', 'jsx'].includes(ext)) return '<i class="fa-brands fa-js text-[#F59E0B]"></i>';
      if (['ts', 'tsx'].includes(ext)) return '<i class="fa-solid fa-code text-[#3B82F6]"></i>';
      if (['html', 'htm'].includes(ext)) return '<i class="fa-brands fa-html5 text-[#EF4444]"></i>';
      if (['css', 'scss', 'sass', 'less'].includes(ext)) return '<i class="fa-brands fa-css3-alt text-[#06B6D4]"></i>';
      if (['json', 'yaml', 'yml', 'toml', 'xml'].includes(ext)) return '<i class="fa-solid fa-gear text-[#A855F7]"></i>';
      if (['exe', 'msi', 'bat', 'cmd', 'ps1'].includes(ext)) return '<i class="fa-solid fa-cube text-[#10B981]"></i>';
      if (['dll', 'sys'].includes(ext)) return '<i class="fa-solid fa-gears text-[#94A3B8]"></i>';
      if (['zip', 'rar', '7z', 'tar', 'gz', 'iso'].includes(ext)) return '<i class="fa-solid fa-file-zipper text-[#EC4899]"></i>';
      if (['md', 'txt', 'rtf', 'log'].includes(ext)) return '<i class="fa-solid fa-file-lines text-[#06B6D4]"></i>';
      if (['pdf'].includes(ext)) return '<i class="fa-solid fa-file-pdf text-[#EF4444]"></i>';
      if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico'].includes(ext)) return '<i class="fa-solid fa-file-image text-[#F43F5E]"></i>';
      return '<i class="fa-regular fa-file text-[#64748B]"></i>';
    }

    function toggleSearchModifier(mod) {
      if (fsModifiers[mod] !== undefined) {
        fsModifiers[mod] = !fsModifiers[mod];
        const btn = document.getElementById(`fs-toggle-${mod}`);
        if (btn) {
          if (fsModifiers[mod]) btn.classList.add('fs-mod-active');
          else btn.classList.remove('fs-mod-active');
        }
        triggerSearch(true);
      }
    }

    function setSearchCategory(cat) {
      fsCategory = cat;
      const pills = ['all', 'code', 'exe', 'doc', 'archive', 'folder'];
      pills.forEach(p => {
        const btn = document.getElementById(`fs-cat-${p}`);
        if (btn) {
          if (p === cat) {
            btn.className = 'fs-cat-pill px-3 py-1 rounded text-xs font-medium bg-[#141721] text-[#3B82F6] border border-[#3B82F640] transition flex items-center gap-1.5';
          } else {
            btn.className = 'fs-cat-pill px-3 py-1 rounded text-xs font-medium text-[#94A3B8] hover:text-[#F3F4F6] bg-[#08090C] border border-[#1F2430] transition flex items-center gap-1.5';
          }
        }
      });
      updateActiveFiltersBadge();
      triggerSearch(true);
    }

    // Helper to inject, replace, or remove a token prefix in the search input
    function setQueryToken(prefix, value, removeRegex) {
      const input = document.getElementById('fs-search-input');
      if (!input) return;
      let q = input.value;
      const regex = removeRegex || new RegExp(`(?:^|\\s)${prefix}[^\\s]*`, 'gi');

      // Clean out existing occurrences of this token
      q = q.replace(regex, ' ').replace(/\s+/g, ' ').trim();

      // If setting a non-empty value, append it cleanly
      if (value) {
        const tokenToAdd = `${prefix}${value}`;
        q = q ? `${q} ${tokenToAdd}` : tokenToAdd;
      }

      input.value = q;
      fsQuery = q;
      const clearBtn = document.getElementById('fs-clear-btn');
      if (clearBtn) {
        if (q.length > 0) clearBtn.classList.remove('hidden');
        else clearBtn.classList.add('hidden');
      }
      syncVisualFiltersFromQuery();
      triggerSearch(true);
    }

    function onVisualFilterChange(target) {
      if (target === 'scope') {
        const scopeSel = document.getElementById('fs-scope-select');
        if (!scopeSel) return;
        const val = scopeSel.value;
        const input = document.getElementById('fs-search-input');
        if (!input) return;

        let q = input.value;
        // Clean existing scope tokens
        const scopeRegex = /(?:^|\s)(?:folder:|dir:|is:folder|is:dir|file:|is:file)\b/gi;
        q = q.replace(scopeRegex, ' ').replace(/\s+/g, ' ').trim();

        if (val === 'files') {
          q = q ? `file: ${q}` : 'file:';
        } else if (val === 'folders') {
          q = q ? `folder: ${q}` : 'folder:';
        }

        input.value = q;
        fsQuery = q;
        const clearBtn = document.getElementById('fs-clear-btn');
        if (clearBtn) {
          if (q.length > 0) clearBtn.classList.remove('hidden');
          else clearBtn.classList.add('hidden');
        }
        syncVisualFiltersFromQuery();
        triggerSearch(true);
      } else if (target === 'size') {
        const sizeSel = document.getElementById('fs-size-select');
        if (!sizeSel) return;
        const val = sizeSel.value;
        setQueryToken('size:', val === 'any' ? null : val, /(?:^|\s)size:[^\s]*/gi);
      } else if (target === 'date') {
        const dateSel = document.getElementById('fs-date-select');
        if (!dateSel) return;
        const val = dateSel.value;
        setQueryToken('dm:', val === 'any' ? null : val, /(?:^|\s)(?:dm:|date:)[^\s]*/gi);
      }
    }

    function setQuickExt(ext) {
      const input = document.getElementById('fs-search-input');
      if (!input) return;
      let q = input.value;
      const extRegex = /(?:^|\s)ext:([^\s]*)/i;
      const match = q.match(extRegex);

      if (match && match[1].toLowerCase() === ext.toLowerCase()) {
        // Toggle off if clicking the already active extension
        q = q.replace(/(?:^|\s)ext:[^\s]*/gi, ' ').replace(/\s+/g, ' ').trim();
      } else {
        // Replace or append
        q = q.replace(/(?:^|\s)ext:[^\s]*/gi, ' ').replace(/\s+/g, ' ').trim();
        q = q ? `${q} ext:${ext}` : `ext:${ext}`;
      }

      input.value = q;
      fsQuery = q;
      const clearBtn = document.getElementById('fs-clear-btn');
      if (clearBtn) {
        if (q.length > 0) clearBtn.classList.remove('hidden');
        else clearBtn.classList.add('hidden');
      }
      syncVisualFiltersFromQuery();
      triggerSearch(true);
    }

    function syncVisualFiltersFromQuery() {
      const q = fsQuery || '';

      // 1. Sync Scope dropdown
      const scopeSel = document.getElementById('fs-scope-select');
      if (scopeSel) {
        if (/(?:^|\s)(?:folder:|dir:|is:folder|is:dir)/i.test(q)) {
          scopeSel.value = 'folders';
        } else if (/(?:^|\s)(?:file:|is:file)/i.test(q)) {
          scopeSel.value = 'files';
        } else {
          scopeSel.value = 'all';
        }
      }

      // 2. Sync Size dropdown
      const sizeSel = document.getElementById('fs-size-select');
      if (sizeSel) {
        const m = q.match(/(?:^|\s)size:([a-z0-9><=.]+)/i);
        if (m && ['empty', 'tiny', 'small', 'medium', 'large', 'huge', 'gigantic'].includes(m[1].toLowerCase())) {
          sizeSel.value = m[1].toLowerCase();
        } else {
          sizeSel.value = 'any';
        }
      }

      // 3. Sync Date dropdown
      const dateSel = document.getElementById('fs-date-select');
      if (dateSel) {
        const m = q.match(/(?:^|\s)(?:dm:|date:)([a-z0-9-]+)/i);
        if (m && ['today', 'yesterday', 'past7', 'past30', 'thisweek', 'thismonth', 'thisyear', 'pastyear'].includes(m[1].toLowerCase())) {
          dateSel.value = m[1].toLowerCase();
        } else {
          dateSel.value = 'any';
        }
      }

      // 4. Sync Quick Ext chips
      const chips = ['py', 'exe', 'json', 'ts', 'md', 'dll'];
      const extMatch = q.match(/(?:^|\s)ext:([a-z0-9;,]+)/i);
      const activeExt = extMatch ? extMatch[1].toLowerCase() : '';
      chips.forEach(c => {
        const el = document.getElementById(`fs-chip-${c}`);
        if (el) {
          if (activeExt === c) el.classList.add('fs-chip-active');
          else el.classList.remove('fs-chip-active');
        }
      });

      updateActiveFiltersBadge();
    }

    function updateActiveFiltersBadge() {
      let count = 0;
      if (fsCategory !== 'all') count++;

      const scopeSel = document.getElementById('fs-scope-select');
      if (scopeSel && scopeSel.value !== 'all') count++;

      const sizeSel = document.getElementById('fs-size-select');
      if (sizeSel && sizeSel.value !== 'any') count++;

      const dateSel = document.getElementById('fs-date-select');
      if (dateSel && dateSel.value !== 'any') count++;

      const chips = ['py', 'exe', 'json', 'ts', 'md', 'dll'];
      const hasActiveChip = chips.some(c => {
        const el = document.getElementById(`fs-chip-${c}`);
        return el && el.classList.contains('fs-chip-active');
      });
      if (hasActiveChip || /(?:^|\s)ext:[^\s]*/i.test(fsQuery)) count++;

      const resetBtn = document.getElementById('fs-reset-filters-btn');
      const countEl = document.getElementById('fs-active-filters-count');
      if (resetBtn && countEl) {
        countEl.innerText = count;
        if (count > 0) resetBtn.classList.remove('hidden');
        else resetBtn.classList.add('hidden');
      }
    }

    function resetAllVisualFilters() {
      fsCategory = 'all';
      setSearchCategory('all');

      const input = document.getElementById('fs-search-input');
      if (input) {
        let q = input.value;
        q = q.replace(/(?:^|\s)(?:folder:|dir:|is:folder|is:dir|file:|is:file)\b/gi, ' ')
             .replace(/(?:^|\s)(?:size:|dm:|date:|ext:)[^\s]*/gi, ' ')
             .replace(/\s+/g, ' ')
             .trim();
        input.value = q;
        fsQuery = q;
        const clearBtn = document.getElementById('fs-clear-btn');
        if (clearBtn) {
          if (q.length > 0) clearBtn.classList.remove('hidden');
          else clearBtn.classList.add('hidden');
        }
      }

      syncVisualFiltersFromQuery();
      triggerSearch(true);
    }

    function clearSearchInput() {
      const input = document.getElementById('fs-search-input');
      if (input) {
        input.value = '';
        fsQuery = '';
        input.focus();
      }
      const clearBtn = document.getElementById('fs-clear-btn');
      if (clearBtn) clearBtn.classList.add('hidden');
      syncVisualFiltersFromQuery();
      triggerSearch(true);
    }

    function toggleSyntaxHelp() {
      const help = document.getElementById('fs-syntax-help');
      if (help) help.classList.toggle('hidden');
    }

    function toggleSearchSort(col) {
      if (fsSortBy === col) {
        fsSortDesc = !fsSortDesc;
      } else {
        fsSortBy = col;
        fsSortDesc = false;
      }
      // Update sort icons
      ['name', 'path', 'size', 'mtime', 'ext'].forEach(c => {
        const icon = document.getElementById(`fs-sort-icon-${c}`);
        if (icon) {
          if (c === fsSortBy) {
            icon.className = fsSortDesc ? 'fa-solid fa-sort-down text-[10px] text-[#3B82F6]' : 'fa-solid fa-sort-up text-[10px] text-[#3B82F6]';
          } else {
            icon.className = 'fa-solid fa-sort text-[10px] text-[#475569]';
          }
        }
      });
      triggerSearch(true);
    }

    function onPageLimitChange() {
      const sel = document.getElementById('fs-limit-select');
      if (sel) {
        fsLimit = parseInt(sel.value, 10) || 100;
        triggerSearch(true);
      }
    }

    function prevSearchPage() {
      if (fsOffset > 0) {
        fsOffset = Math.max(0, fsOffset - fsLimit);
        triggerSearch(false);
      }
    }

    function nextSearchPage() {
      if (fsOffset + fsLimit < fsTotalMatches) {
        fsOffset += fsLimit;
        triggerSearch(false);
      }
    }

    function selectSearchRow(idx) {
      if (fsSelectedRowIndex >= 0) {
        const prev = document.getElementById(`fs-row-${fsSelectedRowIndex}`);
        if (prev) prev.classList.remove('selected');
      }
      fsSelectedRowIndex = idx;
      const current = document.getElementById(`fs-row-${idx}`);
      if (current) {
        current.classList.add('selected');
        current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }

    function navigateSearchRows(delta) {
      if (fsCurrentResults.length === 0) return;
      let nextIdx = fsSelectedRowIndex + delta;
      if (nextIdx < 0) nextIdx = 0;
      if (nextIdx >= fsCurrentResults.length) nextIdx = fsCurrentResults.length - 1;
      selectSearchRow(nextIdx);
    }

    function openSelectedSearchResult() {
      if (fsSelectedRowIndex >= 0 && fsSelectedRowIndex < fsCurrentResults.length) {
        openSearchResult(encodeURIComponent(fsCurrentResults[fsSelectedRowIndex].path));
      }
    }

    async function openSearchResult(encodedPath) {
      const path = decodeURIComponent(encodedPath);
      try {
        const res = await fetch('/api/action/open-file', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: path })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showToast(`Opened: ${path}`);
      } catch (err) {
        console.error('Failed to open file:', err);
        showToast(`Failed to open file: ${err.message}`, true);
      }
    }

    async function revealSearchResult(encodedPath) {
      const path = decodeURIComponent(encodedPath);
      try {
        const res = await fetch('/api/action/reveal-file', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: path })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showToast(`Revealed in Explorer`);
      } catch (err) {
        console.error('Failed to reveal file:', err);
        showToast(`Failed to reveal file: ${err.message}`, true);
      }
    }

    function copySearchResultPath(encodedPath) {
      const path = decodeURIComponent(encodedPath);
      navigator.clipboard.writeText(path).then(() => {
        showToast(`Copied path: ${path}`);
      }).catch(err => {
        showToast(`Failed to copy path`, true);
      });
    }

    function exportSearchResultsCSV() {
      if (!fsCurrentResults || fsCurrentResults.length === 0) {
        showToast('No search results to export', true);
        return;
      }
      let csv = 'Name,Path,Size (Bytes),Size Formatted,Date Modified,Type\n';
      fsCurrentResults.forEach(item => {
        const cleanName = `"${(item.name || '').replace(/"/g, '""')}"`;
        const cleanPath = `"${(item.path || '').replace(/"/g, '""')}"`;
        const size = item.size || 0;
        const sizeFmt = `"${item.size_formatted || ''}"`;
        const mtimeFmt = `"${item.mtime_formatted || ''}"`;
        const ext = `"${item.ext || ''}"`;
        csv += `${cleanName},${cleanPath},${size},${sizeFmt},${mtimeFmt},${ext}\n`;
      });

      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `devtoolkit_search_${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      showToast(`Exported ${fsCurrentResults.length} items to CSV`);
    }

    function copySearchResultsText() {
      if (!fsCurrentResults || fsCurrentResults.length === 0) {
        showToast('No search results to copy', true);
        return;
      }
      const lines = fsCurrentResults.map(item => item.path).join('\n');
      navigator.clipboard.writeText(lines).then(() => {
        showToast(`Copied ${fsCurrentResults.length} paths to clipboard`);
      }).catch(err => {
        showToast('Failed to copy paths', true);
      });
    }

    async function triggerFastSearchReindex() {
      const icon = document.getElementById('fs-reindex-icon');
      const btn = document.getElementById('fs-reindex-btn');
      if (icon) icon.classList.add('fa-spin');
      if (btn) btn.disabled = true;

      const sideStatus = document.getElementById('side-search-status');
      if (sideStatus) sideStatus.innerText = 'Indexing...';
      const sideNavBadge = document.getElementById('side-search-count-badge');
      if (sideNavBadge) {
        sideNavBadge.innerText = 'Indexing...';
        sideNavBadge.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#F59E0B1A] text-[#F59E0B] border border-[#F59E0B40] flex-shrink-0';
      }
      const sideIcon = document.getElementById('side-search-icon');
      if (sideIcon) sideIcon.className = 'fa-solid fa-arrows-rotate fa-spin text-[#F59E0B] text-[10px]';

      try {
        const res = await fetch('/api/search/reindex', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        updateSearchTelemetryUI(data);
        showToast(`Re-indexed ${(data.total_files || 0).toLocaleString()} files in ${data.duration_ms}ms`);
        triggerSearch(true);
      } catch (err) {
        console.error('Fast Search re-index error:', err);
        showToast(`Re-index failed: ${err.message}`, true);
      } finally {
        if (icon) icon.classList.remove('fa-spin');
        if (btn) btn.disabled = false;
      }
    }

    async function loadSystemInfo() {
      try {
        const res = await fetch('/api/system');
        const sys = await res.json();

        // Dynamically update Sidebar OS info & Host name
        const sideOs = document.getElementById('side-os-info');
        if (sideOs) {
          sideOs.innerText = `${sys.os_name} ${sys.os_release} (${sys.arch})`;
          sideOs.title = `${sys.os_name} ${sys.os_release} ${sys.os_version} [${sys.arch}]`;
        }
        const sideHost = document.getElementById('side-host-name');
        if (sideHost) {
          sideHost.innerText = sys.hostname;
          sideHost.title = sys.hostname;
        }
        const sideAppVer = document.getElementById('side-app-version');
        if (sideAppVer && sys.app_version) {
          sideAppVer.innerText = `v${sys.app_version}`;
        }
        const sidePyVer = document.getElementById('side-python-version');
        if (sidePyVer) {
          sidePyVer.innerText = sys.python_version || 'Active';
        }

        // Workstation Telemetry in Help modal
        const sysOs = document.getElementById('sys-os');
        if (sysOs) sysOs.innerText = `${sys.os_name} ${sys.os_release}`;
        const sysArch = document.getElementById('sys-arch');
        if (sysArch) sysArch.innerText = sys.arch;
        const sysHost = document.getElementById('sys-host');
        if (sysHost) sysHost.innerText = sys.hostname;
        const sysPython = document.getElementById('sys-python');
        if (sysPython) sysPython.innerText = sys.python_version || 'Active';

        // Update search engine telemetry
        fetchSearchTelemetry();
      } catch (e) {
        console.error('Error loading system info:', e);
      }
    }

    // Modal Helper
    function toggleHelpModal() {
      const modal = document.getElementById('help-modal');
      modal.classList.toggle('hidden');
    }

    // Keyboard Shortcuts Listeners
    window.addEventListener('keydown', (e) => {
      const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
      const isInput = activeTag === 'input' || activeTag === 'textarea';

      if (e.key === 'Escape') {
        closeExportMenu();
        if (activeDrawerToolId) {
          closeInspectorDrawer();
          return;
        }
        closeKillModal();
        const help = document.getElementById('help-modal');
        if (!help.classList.contains('hidden')) help.classList.add('hidden');
        if (isInput) document.activeElement.blur();
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (activeTab === 'env') {
          const searchInput = document.getElementById('global-search-input');
          if (searchInput) searchInput.focus();
        } else if (activeTab === 'search') {
          const fsInput = document.getElementById('fs-search-input');
          if (fsInput) fsInput.focus();
        } else if (activeTab === 'ports') {
          const portsSearch = document.getElementById('ports-search-input');
          if (portsSearch) portsSearch.focus();
        } else if (activeTab === 'project') {
          const projInput = document.getElementById('project-path-input');
          if (projInput) projInput.focus();
        }
        return;
      }

      // Fast Search table navigation when on Search tab
      if (activeTab === 'search') {
        if (e.altKey) {
          if (e.key.toLowerCase() === 'c') {
            e.preventDefault();
            toggleSearchModifier('case');
            return;
          } else if (e.key.toLowerCase() === 'w') {
            e.preventDefault();
            toggleSearchModifier('word');
            return;
          } else if (e.key.toLowerCase() === 'p') {
            e.preventDefault();
            toggleSearchModifier('path');
            return;
          } else if (e.key.toLowerCase() === 'r') {
            e.preventDefault();
            toggleSearchModifier('regex');
            return;
          }
        }
        if (!isInput) {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            navigateSearchRows(1);
            return;
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            navigateSearchRows(-1);
            return;
          } else if (e.key === 'Enter') {
            e.preventDefault();
            openSelectedSearchResult();
            return;
          } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
            if (fsSelectedRowIndex >= 0 && fsSelectedRowIndex < fsCurrentResults.length) {
              e.preventDefault();
              copySearchResultPath(encodeURIComponent(fsCurrentResults[fsSelectedRowIndex].path));
              return;
            }
          }
        }
      }

      if (!isInput) {
        if (e.key.toLowerCase() === 'r') {
          e.preventDefault();
          refreshActiveTab();
        } else if (e.key === '?') {
          e.preventDefault();
          toggleHelpModal();
        } else if (e.key === '/') {
          e.preventDefault();
          if (activeTab !== 'search') switchTab('search');
          setTimeout(() => {
            const fsInput = document.getElementById('fs-search-input');
            if (fsInput) fsInput.focus();
          }, 60);
        } else if (e.key === '1') {
          switchTab('env');
        } else if (e.key === '2') {
          switchTab('search');
        } else if (e.key === '3') {
          switchTab('ports');
        } else if (e.key === '4') {
          switchTab('project');
        } else if (e.key === '5') {
          switchTab('settings');
        }
      }
    });

    // Initialize Default View
    loadConfig();
    loadSystemInfo();
    fetchSearchTelemetry();
    fetchPorts(false);
    fetchAudit();
    const projInput = document.getElementById('project-path-input');
    if (projInput) projInput.value = '';
    renderRecentProjects();

    // Background Telemetry Polling (4s interval)
    setInterval(fetchSearchTelemetry, 4000);

    // Deep Link & Query Param Support
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const initialTab = urlParams.get('tab');
      if (initialTab && ['env', 'search', 'ports', 'project', 'settings'].includes(initialTab)) {
        switchTab(initialTab);
      }
      const initialAudit = urlParams.get('audit');
      if (initialAudit) {
        setAndAuditProject(initialAudit);
      }
      const initialDrawer = urlParams.get('drawer');
      if (initialDrawer) {
        setTimeout(() => openInspectorDrawer(initialDrawer), 1200);
      }
      const initialHelp = urlParams.get('help');
      if (initialHelp === 'true' || initialHelp === '1') {
        toggleHelpModal();
      }
    } catch (e) {
      console.error('Deep link parsing error:', e);
    }
