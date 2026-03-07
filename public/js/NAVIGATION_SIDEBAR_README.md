# NavigationSidebar Component

## Overview

The `NavigationSidebar` component provides a persistent navigation sidebar for the Fitness Platform V2. It implements responsive behavior with a full sidebar on desktop (≥768px) and a collapsible hamburger menu on mobile (<768px).

## Requirements

- **1.1**: Persistent navigation sidebar on the left side of all pages
- **1.2**: Visible at viewport width ≥ 768px
- **1.3**: Collapses to hamburger menu at viewport width < 768px

## Features

- ✅ Persistent left sidebar navigation
- ✅ Responsive design (desktop/tablet/mobile)
- ✅ Active route highlighting
- ✅ Hamburger menu for mobile devices
- ✅ Smooth animations and transitions
- ✅ Keyboard accessible (Tab, Enter navigation)
- ✅ Screen reader friendly (ARIA labels)
- ✅ Theme toggle integration
- ✅ Auto-closes mobile menu on navigation

## Installation

### 1. Include Required Files

Add the following to your HTML `<head>`:

```html
<!-- Design Tokens (required) -->
<link rel="stylesheet" href="css/design-tokens.css">

<!-- Navigation Sidebar Styles -->
<link rel="stylesheet" href="css/navigation-sidebar.css">
```

### 2. Add Sidebar Container

Add this container element to your HTML body (before main content):

```html
<body>
    <!-- Skip to main content link for accessibility -->
    <a href="#main-content" class="skip-to-main">Skip to main content</a>
    
    <!-- Sidebar Container -->
    <div id="sidebar-container"></div>
    
    <!-- Main Content Area -->
    <main id="main-content" class="main-content">
        <!-- Your page content here -->
    </main>
</body>
```

### 3. Initialize the Component

Add the script at the end of your HTML body:

```html
<!-- Navigation Sidebar Script -->
<script src="js/navigation-sidebar.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', () => {
        const sidebar = new NavigationSidebar('sidebar-container');
    });
</script>
```

## Usage

### Basic Initialization

```javascript
// Initialize with default settings (auto-detects current route)
const sidebar = new NavigationSidebar('sidebar-container');
```

### Custom Route

```javascript
// Initialize with a specific route
const sidebar = new NavigationSidebar('sidebar-container', '/dashboard.html');
```

### Update Active Route Dynamically

```javascript
// Useful for single-page applications
sidebar.setActiveRoute('/activities.html');
```

### Toggle Mobile Menu Programmatically

```javascript
// Open/close mobile menu
sidebar.toggleMobile();
```

## Navigation Items

The sidebar includes the following navigation links:

| Icon | Label       | Path                  |
|------|-------------|-----------------------|
| 📊   | Dashboard   | /index.html           |
| ⚡   | Activities  | /activities.html      |
| 📈   | Metrics     | /measurements.html    |
| 📝   | Logs        | /logs.html            |
| 🎯   | Evaluations | /evaluation.html      |
| 💬   | Chat        | /chat.html            |
| ⚙️   | Settings    | /settings.html        |

## Responsive Behavior

### Desktop (≥768px)
- Sidebar is always visible on the left
- Width: 16rem (256px)
- Main content has left margin to accommodate sidebar
- Navigation labels are visible

### Mobile (<768px)
- Sidebar is hidden by default
- Hamburger menu button appears in top-left
- Clicking hamburger slides sidebar in from left
- Overlay appears behind sidebar
- Clicking overlay or navigation link closes menu
- Body scroll is disabled when menu is open

### Very Small Screens (<640px)
- Sidebar width reduces to 4rem (64px)
- Only icons are shown (labels hidden)

## Accessibility Features

### Keyboard Navigation
- All interactive elements are keyboard accessible
- Tab key navigates through menu items
- Enter key activates links
- Focus indicators are clearly visible

### Screen Reader Support
- ARIA labels on all buttons
- `aria-current="page"` on active navigation item
- Skip to main content link for bypassing navigation
- Semantic HTML structure

### Color Contrast
- Meets WCAG 2.1 AA standards (4.5:1 contrast ratio)
- Focus indicators have sufficient contrast
- Active states are clearly distinguishable

## Customization

### Modify Navigation Items

Edit the `navItems` array in the constructor:

```javascript
this.navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊', path: '/index.html' },
  { id: 'custom', label: 'Custom Page', icon: '🔧', path: '/custom.html' },
  // Add more items...
];
```

### Styling

Override CSS variables in your custom stylesheet:

```css
:root {
  --sidebar-width: 18rem;  /* Change sidebar width */
  --navbar-height: 5rem;   /* Change header height */
}
```

### Theme Integration

The sidebar automatically uses the current DaisyUI theme. Toggle theme with:

```javascript
document.documentElement.setAttribute('data-theme', 'dark');
```

## Browser Support

- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- Mobile browsers: ✅ Full support

## Performance

- Minimal JavaScript footprint (~5KB)
- CSS animations use GPU acceleration
- No external dependencies (except DaisyUI/Tailwind)
- Efficient event listeners (no memory leaks)

## Example

See `sidebar-demo.html` for a complete working example.

## API Reference

### Constructor

```javascript
new NavigationSidebar(containerId, currentRoute)
```

**Parameters:**
- `containerId` (string): ID of the container element
- `currentRoute` (string, optional): Current route path (auto-detected if omitted)

### Methods

#### `render()`
Renders the sidebar HTML into the container.

```javascript
sidebar.render();
```

#### `setActiveRoute(route)`
Updates the active route and re-renders the sidebar.

```javascript
sidebar.setActiveRoute('/activities.html');
```

**Parameters:**
- `route` (string): New active route path

#### `toggleMobile()`
Toggles the mobile menu open/closed state.

```javascript
sidebar.toggleMobile();
```

### Properties

#### `navItems`
Array of navigation item objects.

```javascript
sidebar.navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊', path: '/index.html' }
];
```

#### `currentRoute`
Current active route path.

```javascript
console.log(sidebar.currentRoute); // '/index.html'
```

#### `isMobileMenuOpen`
Boolean indicating mobile menu state.

```javascript
console.log(sidebar.isMobileMenuOpen); // true or false
```

## Troubleshooting

### Sidebar not appearing
- Ensure `design-tokens.css` is loaded before `navigation-sidebar.css`
- Check that container element exists: `document.getElementById('sidebar-container')`
- Verify JavaScript is loaded after DOM is ready

### Active route not highlighting
- Check that route paths match exactly (case-sensitive)
- Ensure `currentRoute` is set correctly
- Verify path format (should start with `/`)

### Mobile menu not working
- Check browser console for JavaScript errors
- Ensure event listeners are attached (call `render()` after initialization)
- Verify viewport meta tag is present in HTML head

## License

Part of the Fitness Platform V2 project.
