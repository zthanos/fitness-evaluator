# Navigation Sidebar Integration Guide

## Quick Start

This guide shows how to integrate the NavigationSidebar component into existing pages.

## Step-by-Step Integration

### 1. Update HTML Head

Add the required CSS files to your page's `<head>` section:

```html
<head>
    <!-- Existing head content... -->
    
    <!-- Design Tokens (if not already included) -->
    <link rel="stylesheet" href="css/design-tokens.css">
    
    <!-- Navigation Sidebar Styles -->
    <link rel="stylesheet" href="css/navigation-sidebar.css">
</head>
```

### 2. Update HTML Body Structure

Replace the old navbar with the new sidebar structure:

**Before:**
```html
<body class="bg-base-200">
    <div class="min-h-screen">
        <!-- Old Navbar -->
        <div class="navbar bg-base-100 shadow-md">
            <!-- navbar content -->
        </div>
        
        <!-- Main Content -->
        <div class="container mx-auto p-4">
            <!-- page content -->
        </div>
    </div>
</body>
```

**After:**
```html
<body class="bg-base-200">
    <!-- Skip to main content link for accessibility -->
    <a href="#main-content" class="skip-to-main">Skip to main content</a>
    
    <!-- Sidebar Container -->
    <div id="sidebar-container"></div>
    
    <!-- Main Content Area -->
    <main id="main-content" class="main-content">
        <div class="container mx-auto p-4 max-w-6xl">
            <!-- page content -->
        </div>
    </main>
</body>
```

### 3. Add Initialization Script

Add the sidebar initialization script before the closing `</body>` tag:

```html
    <!-- Navigation Sidebar Script -->
    <script src="js/navigation-sidebar.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const sidebar = new NavigationSidebar('sidebar-container');
        });
    </script>
</body>
```

### 4. Remove Old Navigation

Remove or comment out the old navbar code:

```html
<!-- OLD NAVBAR - REMOVE THIS
<div class="navbar bg-base-100 shadow-md">
    <div class="flex-1">
        <a href="index.html" class="btn btn-ghost text-xl">💪 Fitness Evaluator</a>
    </div>
    ...
</div>
-->
```

## Example: Converting index.html

Here's a complete example of converting the existing `index.html`:

```html
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fitness Platform - Dashboard</title>
    
    <!-- DaisyUI and Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4.4.20/dist/full.min.css" rel="stylesheet" type="text/css" />
    
    <!-- Design Tokens -->
    <link rel="stylesheet" href="css/design-tokens.css">
    
    <!-- Navigation Sidebar Styles -->
    <link rel="stylesheet" href="css/navigation-sidebar.css">
</head>
<body class="bg-base-200">
    <!-- Skip to main content link -->
    <a href="#main-content" class="skip-to-main">Skip to main content</a>
    
    <!-- Sidebar Container -->
    <div id="sidebar-container"></div>
    
    <!-- Main Content Area -->
    <main id="main-content" class="main-content">
        <div class="container mx-auto p-4 max-w-6xl">
            <!-- Your existing page content goes here -->
            <h1 class="text-4xl font-bold mb-6">Dashboard</h1>
            
            <!-- Stats, cards, etc. -->
        </div>
    </main>

    <!-- Existing scripts -->
    <script src="js/api.js"></script>
    <script src="js/utils.js"></script>
    
    <!-- Navigation Sidebar Script -->
    <script src="js/navigation-sidebar.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const sidebar = new NavigationSidebar('sidebar-container');
            
            // Your existing initialization code...
        });
    </script>
</body>
</html>
```

## Pages to Update

Apply this integration to all pages:

- ✅ `index.html` (Dashboard)
- ⬜ `activities.html` (to be created)
- ⬜ `measurements.html` (Metrics)
- ⬜ `logs.html` (Daily Logs)
- ⬜ `evaluation.html` (Evaluations)
- ⬜ `chat.html` (to be created)
- ⬜ `settings.html` (to be created)
- ⬜ `targets.html` (Plan Targets)

## Testing Checklist

After integration, verify:

### Desktop (≥768px)
- [ ] Sidebar is visible on the left
- [ ] Sidebar width is 16rem (256px)
- [ ] Main content has proper left margin
- [ ] Active page is highlighted in sidebar
- [ ] All navigation links work
- [ ] Theme toggle button works

### Tablet (768px - 1023px)
- [ ] Sidebar remains visible
- [ ] Content layout is responsive
- [ ] Navigation is accessible

### Mobile (<768px)
- [ ] Hamburger menu button appears in top-left
- [ ] Sidebar is hidden by default
- [ ] Clicking hamburger opens sidebar
- [ ] Overlay appears behind sidebar
- [ ] Clicking overlay closes sidebar
- [ ] Clicking nav link closes sidebar
- [ ] Body scroll is disabled when menu is open

### Accessibility
- [ ] Tab key navigates through menu items
- [ ] Enter key activates links
- [ ] Focus indicators are visible
- [ ] Skip to main content link works
- [ ] Screen reader announces navigation items

## Common Issues

### Issue: Sidebar overlaps content on desktop
**Solution:** Ensure the main content has the `main-content` class:
```html
<main id="main-content" class="main-content">
```

### Issue: Mobile menu doesn't close
**Solution:** Check that the sidebar script is loaded after the DOM:
```javascript
document.addEventListener('DOMContentLoaded', () => {
    const sidebar = new NavigationSidebar('sidebar-container');
});
```

### Issue: Active route not highlighting
**Solution:** Ensure the current page path matches the navigation item path exactly:
- Use `/index.html` not `/` or `index.html`
- Paths are case-sensitive

### Issue: Styles not applying
**Solution:** Verify CSS load order:
1. design-tokens.css (first)
2. navigation-sidebar.css (second)

## Demo Page

See `sidebar-demo.html` for a complete working example with sample content.

## Next Steps

1. Integrate sidebar into all existing pages
2. Create new pages (activities.html, chat.html, settings.html)
3. Test responsive behavior across devices
4. Verify accessibility with screen readers
5. Update any page-specific navigation logic

## Support

For detailed API documentation, see `public/js/NAVIGATION_SIDEBAR_README.md`.
