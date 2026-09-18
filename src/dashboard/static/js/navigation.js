/**
 * ChainC2 Sentinel — Single Page Application Navigation Manager
 * Handles tab routing, state management, and section activation without page reloads.
 */

class NavigationManager {
  constructor() {
    this.currentSection = 'overview';
    this.subscribers = [];
    this.init();
  }

  init() {
    // Listen for hash change in URL
    window.addEventListener('hashchange', () => this.handleHashChange());

    // Attach click events to nav links
    document.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const target = link.getAttribute('data-target');
        if (target) {
          window.location.hash = target;
        }
      });
    });

    // Initial route
    this.handleHashChange();
  }

  handleHashChange() {
    const hash = window.location.hash.replace('#', '').trim();
    const targetSection = hash || 'overview';
    this.navigateTo(targetSection);
  }

  navigateTo(sectionId) {
    const targetElement = document.getElementById(`section-${sectionId}`);
    if (!targetElement) {
      console.warn(`Section '${sectionId}' not found. Defaulting to overview.`);
      sectionId = 'overview';
    }

    this.currentSection = sectionId;

    // Update active class on sections
    document.querySelectorAll('.dashboard-section').forEach(sec => {
      sec.classList.remove('active');
    });
    const activeSection = document.getElementById(`section-${sectionId}`);
    if (activeSection) {
      activeSection.classList.add('active');
    }

    // Update active class on nav links
    document.querySelectorAll('.nav-link').forEach(link => {
      if (link.getAttribute('data-target') === sectionId) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    // Update page header title
    const pageTitleEl = document.getElementById('current-page-title');
    if (pageTitleEl) {
      const titles = {
        'overview': 'Executive Research Overview',
        'experiment-center': 'Laboratory Experiment Center',
        'live-telemetry': 'Telemetry Event Stream',
        'correlation': 'Cross-Layer Sequence Correlation',
        'detection': 'Explainable Rule-Based Detection & Scoring',
        'protection': 'Phase 2 Defensive Response & Containment',
        'evaluation': 'Empirical Evaluation & Performance Analytics',
        'history': 'Experiment Run History & Forensic Chain',
        'evidence': 'Forensic Evidence Explorer & SHA-256 Audit',
        'research': 'Research Synthesis, Observations & Reports',
      };
      pageTitleEl.textContent = titles[sectionId] || 'ChainC2 Sentinel';
    }

    // Notify registered section listeners
    this.subscribers.forEach(cb => cb(sectionId));
  }

  onSectionChange(callback) {
    this.subscribers.push(callback);
  }
}

window.navManager = new NavigationManager();
