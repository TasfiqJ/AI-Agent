/**
 * test-guardian Dashboard — Alpine.js application
 */

function dashboard() {
    return {
        // Navigation
        activeTab: 'scanner',
        tabs: [
            { id: 'scanner', label: 'Scanner', icon: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>' },
            { id: 'run', label: 'Agent Run', icon: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' },
            { id: 'results', label: 'Test Results', icon: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' },
            { id: 'eval', label: 'Evaluation', icon: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>' },
            { id: 'history', label: 'History', icon: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' },
        ],

        // Connection
        connected: false,

        // Scanner
        scanPath: '',
        scanning: false,
        scanResult: null,
        quickPaths: [
            { label: 'flask-todo-api', path: './demo/flask-todo-api' },
            { label: 'fastapi-notes', path: './demo/fastapi-notes' },
            { label: 'express-users-api', path: './demo/express-users-api' },
        ],

        // Agent Run
        runConfig: {
            path: '',
            mode: 'trust',
            maxIterations: 3,
            model: 'qwen2.5-coder:7b',
        },
        running: false,
        currentState: 'IDLE',
        runLogs: [],
        runId: null,
        eventSource: null,
        pipelineStates: ['IDLE', 'PLANNING', 'ACTING', 'VERIFYING', 'COMPLETE'],
        stateIcons: {
            'IDLE': '~',
            'PLANNING': 'P',
            'ACTING': 'A',
            'VERIFYING': 'V',
            'COMPLETE': '\u2713',
            'FAILED': '\u2717',
            'REVERTED': '\u21A9',
        },

        // Test Results
        testResults: [],
        filesChanged: [],

        // Evaluation
        evalRunning: false,
        evalResult: null,

        // History
        scanHistory: [],
        runHistory: [],

        // Browse modal
        browseOpen: false,
        browseTarget: 'scan',   // 'scan' or 'run'
        browseCurrent: '',
        browseParent: '',
        browseItems: [],
        browseLoading: false,
        browseError: null,

        // ── Lifecycle ──

        init() {
            this.checkConnection();
            setInterval(() => this.checkConnection(), 5000);
            this.loadHistory();
        },

        // ── Connection ──

        async checkConnection() {
            try {
                const resp = await fetch('/dashboard/api/ping');
                this.connected = resp.ok;
            } catch {
                this.connected = false;
            }
        },

        // ── Scanner ──

        async scanProject() {
            if (!this.scanPath || this.scanning) return;

            this.scanning = true;
            this.scanResult = null;

            try {
                const resp = await fetch('/dashboard/api/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ repo_path: this.scanPath }),
                });

                if (!resp.ok) throw new Error(`Scan failed: ${resp.status}`);

                this.scanResult = await resp.json();
                this.runConfig.path = this.scanPath;
                this.loadHistory();
            } catch (err) {
                alert('Scan failed: ' + err.message);
            } finally {
                this.scanning = false;
            }
        },

        // ── Agent Run ──

        isStatePast(state) {
            const order = ['IDLE', 'PLANNING', 'ACTING', 'VERIFYING', 'COMPLETE'];
            const currentIdx = order.indexOf(this.currentState);
            const stateIdx = order.indexOf(state);
            if (currentIdx < 0 || stateIdx < 0) return false;
            return stateIdx < currentIdx;
        },

        addLog(type, message) {
            const icons = { state: '\u25CF', tool: '\u2022', info: '\u203A', error: '\u2717', success: '\u2713' };
            this.runLogs.push({
                type,
                message,
                icon: icons[type] || '\u203A',
                time: new Date().toLocaleTimeString(),
            });

            // Auto-scroll
            this.$nextTick(() => {
                const container = this.$refs.logContainer;
                if (container) container.scrollTop = container.scrollHeight;
            });
        },

        async startRun() {
            if (!this.runConfig.path) return;

            this.running = true;
            this.currentState = 'IDLE';
            this.runLogs = [];
            this.testResults = [];

            this.addLog('info', 'Starting agent run...');

            try {
                // Step 1: Start the run
                const resp = await fetch('/dashboard/api/run/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        repo_path: this.runConfig.path,
                        permission_mode: this.runConfig.mode,
                        max_iterations: parseInt(this.runConfig.maxIterations),
                        model: this.runConfig.model,
                    }),
                });

                if (!resp.ok) throw new Error('Failed to start run');

                const data = await resp.json();
                this.runId = data.run_id;
                this.addLog('info', `Run ID: ${this.runId}`);

                // Step 2: Connect to SSE
                this.eventSource = new EventSource(`/dashboard/api/run/events/${this.runId}`);

                this.eventSource.addEventListener('state_change', (e) => {
                    const d = JSON.parse(e.data);
                    this.currentState = d.to_state;
                    this.addLog('state', `${d.from_state} \u2192 ${d.to_state}`);
                });

                this.eventSource.addEventListener('plan_generated', (e) => {
                    const d = JSON.parse(e.data);
                    this.addLog('success', `Plan: ${d.endpoints_count} endpoints, ${d.steps_count} steps`);
                });

                this.eventSource.addEventListener('iteration_start', (e) => {
                    const d = JSON.parse(e.data);
                    this.addLog('info', `Iteration ${d.iteration}/${d.max_iterations}`);
                });

                this.eventSource.addEventListener('test_result', (e) => {
                    const d = JSON.parse(e.data);
                    this.addLog(d.all_pass ? 'success' : 'error',
                        d.all_pass ? 'All tests passed!' : 'Tests failed, retrying...');
                });

                this.eventSource.addEventListener('run_complete', (e) => {
                    const d = JSON.parse(e.data);
                    this.running = false;
                    this.currentState = d.state || 'COMPLETE';
                    this.testResults = d.test_results || [];
                    this.filesChanged = d.files_changed || [];
                    this.addLog('success', `Run complete: ${d.termination_reason || d.state}`);
                    this.eventSource.close();
                    this.loadHistory();
                });

                this.eventSource.addEventListener('error', (e) => {
                    if (e.data) {
                        const d = JSON.parse(e.data);
                        this.addLog('error', d.error || 'Unknown error');
                    }
                    this.running = false;
                    this.eventSource.close();
                });

                this.eventSource.onerror = () => {
                    if (this.running) {
                        this.addLog('info', 'Stream ended');
                        this.running = false;
                    }
                    this.eventSource.close();
                };

            } catch (err) {
                this.addLog('error', err.message);
                this.running = false;
            }
        },

        // ── Browse ──

        async openBrowse(target) {
            this.browseTarget = target || 'scan';
            this.browseOpen = true;
            this.browseError = null;
            await this.browseTo('');
        },

        async browseTo(path) {
            this.browseLoading = true;
            this.browseError = null;

            try {
                const resp = await fetch('/dashboard/api/browse?path=' + encodeURIComponent(path));
                if (!resp.ok) throw new Error('Browse failed');
                const data = await resp.json();

                this.browseCurrent = data.current || '';
                this.browseParent = data.parent || '';
                this.browseItems = data.items || [];
                if (data.error) this.browseError = data.error;
            } catch (err) {
                this.browseError = err.message;
            } finally {
                this.browseLoading = false;
            }
        },

        selectFolder() {
            if (!this.browseCurrent) return;

            if (this.browseTarget === 'scan') {
                this.scanPath = this.browseCurrent;
            } else if (this.browseTarget === 'run') {
                this.runConfig.path = this.browseCurrent;
            }

            this.browseOpen = false;
        },

        browseBreadcrumbs() {
            if (!this.browseCurrent) return [{ label: 'My Computer', path: '' }];

            const parts = this.browseCurrent.replace(/\\/g, '/').split('/').filter(Boolean);
            const crumbs = [{ label: 'My Computer', path: '' }];
            let accumulated = '';

            for (const part of parts) {
                // Handle Windows drive letters (e.g., "C:")
                if (accumulated === '') {
                    accumulated = part.includes(':') ? part + '\\' : '/' + part;
                } else {
                    accumulated += (accumulated.endsWith('\\') ? '' : '\\') + part;
                }
                crumbs.push({ label: part, path: accumulated });
            }

            return crumbs;
        },

        // ── Evaluation ──

        async runEval(includeExternal) {
            this.evalRunning = true;
            this.evalResult = null;

            try {
                const resp = await fetch('/dashboard/api/eval', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ include_external: includeExternal }),
                });

                if (!resp.ok) throw new Error(`Eval failed: ${resp.status}`);

                this.evalResult = await resp.json();
            } catch (err) {
                alert('Evaluation failed: ' + err.message);
            } finally {
                this.evalRunning = false;
            }
        },

        // ── History ──

        async loadHistory() {
            try {
                const resp = await fetch('/dashboard/api/history');
                if (resp.ok) {
                    const data = await resp.json();
                    this.scanHistory = data.scans || [];
                    this.runHistory = data.runs || [];
                }
            } catch {
                // silently fail
            }
        },
    };
}
