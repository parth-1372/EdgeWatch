# EdgeWatch Visual Identity and Branding Guide

## Logo and Brand Colors

### Primary Colors
- **EdgeWatch Blue:** `#2563EB` (Primary brand color)
- **Monitor Green:** `#059669` (Success, healthy status)
- **Alert Orange:** `#EA580C` (Warnings, medium alerts)
- **Critical Red:** `#DC2626` (Errors, critical alerts)

### Secondary Colors
- **Dark Navy:** `#1E293B` (Text, headers)
- **Light Gray:** `#F8FAFC` (Backgrounds)
- **Medium Gray:** `#64748B` (Secondary text)
- **Border Gray:** `#E2E8F0` (Borders, dividers)

### Typography
- **Primary Font:** Inter (Web), -apple-system (Fallback)
- **Monospace Font:** 'Monaco', 'Menlo', 'Ubuntu Mono', monospace
- **Icon Font:** Lucide Icons

## Logo Specifications

### Primary Logo
```
EdgeWatch
```
- Font: Inter Bold, 32px
- Color: EdgeWatch Blue (#2563EB)
- Usage: Main branding, headers, documentation

### Logo with Icon
```
📡 EdgeWatch
```
- Icon: Radar/Satellite symbol
- Represents: Monitoring, networking, edge computing
- Usage: Dashboard, applications, marketing

### Monochrome Versions
- **Dark backgrounds:** White logo
- **Light backgrounds:** Dark navy logo
- **Minimum size:** 120px width for readability

## Dashboard Design System

### Layout Grid
- **Container:** 1200px max-width, centered
- **Columns:** 12-column grid system
- **Gutters:** 24px between columns
- **Margins:** 32px on large screens, 16px on mobile

### Components

#### Cards
```css
.card {
  background: white;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  padding: 24px;
}
```

#### Buttons
```css
.btn-primary {
  background: #2563EB;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-weight: 500;
}

.btn-success {
  background: #059669;
  color: white;
}

.btn-warning {
  background: #EA580C;
  color: white;
}

.btn-danger {
  background: #DC2626;
  color: white;
}
```

#### Status Indicators
```css
.status-online {
  background: #059669;
  color: white;
}

.status-offline {
  background: #DC2626;
  color: white;
}

.status-warning {
  background: #EA580C;
  color: white;
}

.status-unknown {
  background: #64748B;
  color: white;
}
```

## Iconography

### System Icons
- **Dashboard:** 📊 (Chart, Analytics)
- **Nodes:** 🖥️ (Computer, Server)
- **Metrics:** 📈 (Trending Up)
- **Alerts:** ⚠️ (Warning Triangle)
- **Settings:** ⚙️ (Gear)
- **Health:** ❤️ (Heart, Pulse)
- **Network:** 🌐 (Globe, Network)
- **Security:** 🔒 (Lock)

### Status Icons
- **Online/Healthy:** ✅ (Green Check)
- **Offline/Error:** ❌ (Red X)
- **Warning:** ⚠️ (Yellow Warning)
- **Unknown:** ❓ (Gray Question)
- **Loading:** ⏳ (Hourglass, Spinner)

### Action Icons
- **Edit:** ✏️ (Pencil)
- **Delete:** 🗑️ (Trash)
- **Add:** ➕ (Plus)
- **Search:** 🔍 (Magnifying Glass)
- **Filter:** 🔽 (Filter)
- **Export:** 📤 (Upload)
- **Import:** 📥 (Download)

## Data Visualization

### Chart Colors
1. **Primary Series:** #2563EB (EdgeWatch Blue)
2. **Secondary Series:** #059669 (Monitor Green)
3. **Tertiary Series:** #EA580C (Alert Orange)
4. **Additional Series:** #8B5CF6, #06B6D4, #84CC16

### Chart Types
- **Line Charts:** Time series data, metrics over time
- **Bar Charts:** Comparative data, resource usage
- **Pie Charts:** Distribution data, status breakdowns
- **Gauge Charts:** Real-time metrics, thresholds
- **Heatmaps:** Network topology, correlation matrices

## Dashboard Layout Examples

### Main Dashboard
```
+----------------------------------+
|  EdgeWatch Logo    [User Menu]   |
+----------------------------------+
| [Nav] | System Overview          |
|  📊   | +----------+----------+  |
|  🖥️   | | Nodes    | Alerts  |  |
|  📈   | | 15 Total | 3 Active|  |
|  ⚠️   | +----------+----------+  |
|  ⚙️   | Performance Metrics     |
|       | [Line Chart]            |
|       | Recent Activity         |
|       | [Activity Feed]         |
+----------------------------------+
```

### Node Detail View
```
+----------------------------------+
| ← Back | edge-server-01    [⚙️]  |
+----------------------------------+
| Status: ✅ Online               |
| IP: 192.168.1.100 Port: 8080    |
+----------------------------------+
| CPU Usage    Memory    Disk      |
| [Gauge 75%]  [Gauge]   [Gauge]   |
+----------------------------------+
| Metrics History                  |
| [Multi-line Chart]               |
+----------------------------------+
| Recent Alerts                    |
| [Alert List]                     |
+----------------------------------+
```

## Mobile Responsive Design

### Breakpoints
- **Mobile:** 320px - 768px
- **Tablet:** 768px - 1024px
- **Desktop:** 1024px+

### Mobile Adaptations
- Collapsible navigation menu
- Stacked card layouts
- Touch-friendly button sizes (44px minimum)
- Simplified charts and data displays
- Swipe gestures for navigation

## Accessibility Guidelines

### Color Contrast
- Text on background: Minimum 4.5:1 ratio
- Large text (18px+): Minimum 3:1 ratio
- Status indicators: Use icons + color
- Color-blind friendly palette

### Interactive Elements
- Focus indicators on all interactive elements
- Keyboard navigation support
- Screen reader friendly labels
- Alternative text for all images and icons

### Content Structure
- Proper heading hierarchy (h1, h2, h3)
- Semantic HTML elements
- Descriptive link text
- Form labels and error messages

## Animation and Interactions

### Micro-interactions
```css
.btn {
  transition: all 0.2s ease;
}

.btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.card {
  transition: box-shadow 0.3s ease;
}

.card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
```

### Loading States
- Skeleton loading for content
- Spinner for actions
- Progress bars for uploads/downloads
- Smooth transitions between states

### Page Transitions
- Fade in/out between views
- Slide animations for modals
- Smooth scrolling for navigation
- Loading indicators for async operations

## Print Styles

### Report Formatting
```css
@media print {
  .no-print { display: none; }
  .page-break { page-break-before: always; }
  body { font-size: 12pt; }
  h1 { font-size: 18pt; }
  h2 { font-size: 16pt; }
}
```

### Printable Elements
- Dashboard summaries
- Alert reports
- Node configuration sheets
- Performance reports

## Brand Voice and Messaging

### Tone
- **Professional:** Clear, authoritative technical communication
- **Helpful:** Solution-oriented, user-focused
- **Reliable:** Consistent, trustworthy, stable
- **Modern:** Contemporary, forward-thinking

### Key Messages
- "Monitor your edge infrastructure with confidence"
- "Real-time insights for distributed systems"
- "Reliable monitoring for the edge computing era"
- "Comprehensive visibility across your network"

### Content Guidelines
- Use active voice
- Keep sentences concise
- Avoid unnecessary jargon
- Include practical examples
- Focus on user benefits

## File Naming Conventions

### Image Assets
- `logo-primary.svg` - Main logo
- `logo-monochrome.svg` - Single color version
- `icon-dashboard.svg` - Dashboard icon
- `chart-template.png` - Chart examples
- `screenshot-main-dashboard.png` - Product screenshots

### CSS Classes
- `.edgewatch-` prefix for components
- `.status-` prefix for status indicators
- `.metric-` prefix for metric displays
- `.alert-` prefix for alert components

This visual identity guide ensures consistent branding across all EdgeWatch materials, from the web dashboard to documentation and marketing materials.
