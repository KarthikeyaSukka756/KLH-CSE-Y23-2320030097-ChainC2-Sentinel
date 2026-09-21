/**
 * ChainC2 Sentinel — Single Page Application Navigation Manager
 * Handles tab routing, state management, and section activation without page reloads.
 */

class NavigationManager {
  constructor() {
    this.currentSection = 'overview';
    this.subscribers = [];
    this._initialized = false;
    this.init();
  }

  init() {
    if (this._initialized) {
      this.handleHashChange();
      return;
    }
    this._initialized = true;

    // Listen for hash change in URL
    window.addEventListener('hashchange', () => this.handleHashChange());

    // Attach click events to nav links/items
    document.querySelectorAll('.nav-link, .nav-item').forEach(link => {
      link.addEventListener('click', (e) => {
        const target = link.getAttribute('data-section') ||
                       link.getAttribute('data-target') ||
                       link.getAttribute('href')?.replace('#', '');
        if (target) {
          e.preventDefault();
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
    // Resolve section element matching sec-${id} or section-${id} or ${id}
    const targetElement = document.getElementById(`sec-${sectionId}`) ||
                          document.getElementById(`section-${sectionId}`) ||
                          document.getElementById(sectionId);

    if (!targetElement) {
      console.warn(`Section '${sectionId}' not found. Defaulting to overview.`);
      sectionId = 'overview';
    }

    this.currentSection = sectionId;

    // Update active class on sections
    document.querySelectorAll('.dashboard-section, .spa-section').forEach(sec => {
      sec.classList.remove('active');
    });
    const activeSection = document.getElementById(`sec-${sectionId}`) ||
                          document.getElementById(`section-${sectionId}`) ||
                          document.getElementById(sectionId);
    if (activeSection) {
      activeSection.classList.add('active');
    }

    // Update active class on nav links/items
    document.querySelectorAll('.nav-link, .nav-item').forEach(link => {
      const linkTarget = link.getAttribute('data-section') ||
                         link.getAttribute('data-target') ||
                         link.getAttribute('href')?.replace('#', '');
      if (linkTarget === sectionId) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    // Update page header title if element is present
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
        'experiment-history': 'Experiment Run History & Forensic Chain',
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

const navManagerInstance = new NavigationManager();
window.navManager = navManagerInstance;
window.Navigation = navManagerInstance;
var Navigation = navManagerInstance;
var navManager = navManagerInstance;
