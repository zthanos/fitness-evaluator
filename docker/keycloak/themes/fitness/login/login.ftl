<!DOCTYPE html>
<html lang="${locale!'en'}">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>${msg("loginTitle", realm.displayName!'Fitness Platform')}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #4c1d95 0%, #7C3AED 40%, #2563EB 100%);
      padding: 1.5rem;
    }
    .card {
      background: #fff;
      border-radius: 1.25rem;
      box-shadow: 0 25px 60px rgba(0,0,0,0.30);
      padding: 2.5rem 2rem;
      width: 100%;
      max-width: 420px;
    }
    .brand {
      display: flex;
      justify-content: center;
      align-items: baseline;
      gap: 4px;
      font-size: 1.5rem;
      font-weight: 800;
      margin-bottom: 0.25rem;
    }
    .brand-fitness  { color: #7C3AED; }
    .brand-platform { color: #2563EB; }
    .card-title {
      text-align: center;
      font-size: 1.125rem;
      font-weight: 600;
      color: #1e1b4b;
      margin-bottom: 0.25rem;
    }
    .card-subtitle {
      text-align: center;
      font-size: 0.8125rem;
      color: #6b7280;
      margin-bottom: 1.75rem;
    }
    .alert {
      border-radius: 0.625rem;
      padding: 0.75rem 1rem;
      font-size: 0.8125rem;
      margin-bottom: 1.25rem;
      font-weight: 500;
    }
    .alert-error   { background: #fee2e2; color: #991b1b; }
    .alert-warning { background: #fef9c3; color: #854d0e; }
    .alert-info    { background: #dbeafe; color: #1e40af; }
    .alert-success { background: #dcfce7; color: #166534; }
    .form-group { margin-bottom: 1rem; }
    label {
      display: block;
      font-size: 0.8125rem;
      font-weight: 600;
      color: #374151;
      margin-bottom: 0.375rem;
    }
    input[type=text], input[type=email], input[type=password] {
      width: 100%;
      padding: 0.625rem 0.875rem;
      border: 1.5px solid #d1d5db;
      border-radius: 0.5rem;
      font-family: 'Inter', sans-serif;
      font-size: 0.9375rem;
      color: #111827;
      outline: none;
      transition: border-color 0.15s;
    }
    input[type=text]:focus, input[type=email]:focus, input[type=password]:focus {
      border-color: #7C3AED;
      box-shadow: 0 0 0 3px rgba(124,58,237,0.12);
    }
    .field-error { font-size: 0.75rem; color: #dc2626; margin-top: 0.25rem; }
    .input-invalid { border-color: #ef4444 !important; }
    .remember-row { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1.25rem; }
    .remember-row input[type=checkbox] { accent-color: #7C3AED; width: 1rem; height: 1rem; }
    .remember-row label { margin: 0; font-size: 0.8125rem; font-weight: 500; color: #374151; }
    .btn-primary {
      display: block;
      width: 100%;
      padding: 0.75rem;
      background: #7C3AED;
      color: #fff;
      border: none;
      border-radius: 0.625rem;
      font-family: 'Inter', sans-serif;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.15s;
      margin-bottom: 1.25rem;
    }
    .btn-primary:hover { background: #6d28d9; }
    .links { display: flex; flex-direction: column; gap: 0.625rem; text-align: center; }
    .links a { font-size: 0.8125rem; color: #7C3AED; text-decoration: none; font-weight: 500; }
    .links a:hover { text-decoration: underline; }
    .register-link { text-align: center; margin-top: 1rem; font-size: 0.8125rem; color: #6b7280; }
    .register-link a { color: #7C3AED; font-weight: 600; text-decoration: none; }
    .register-link a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">

    <div class="brand">
      <span class="brand-fitness">Fitness</span>
      <span class="brand-platform">Platform</span>
    </div>
    <p class="card-title">Welcome back</p>
    <p class="card-subtitle">Sign in to your account to continue</p>

    <#if message?has_content>
      <div class="alert alert-${message.type}">${message.summary?no_esc}</div>
    </#if>

    <form action="${url.loginAction}" method="post">

      <div class="form-group">
        <label for="username">
          <#if realm.loginWithEmailAllowed?? && realm.loginWithEmailAllowed>Email<#else>Username</#if>
        </label>
        <input type="text" id="username" name="username"
          value="${login.username!''}"
          autofocus autocomplete="username"
          class="<#if messagesPerField.existsError('username','password')>input-invalid</#if>" />
        <#if messagesPerField.existsError('username')>
          <div class="field-error">${messagesPerField.get('username')?no_esc}</div>
        </#if>
      </div>

      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password"
          autocomplete="current-password"
          class="<#if messagesPerField.existsError('password')>input-invalid</#if>" />
        <#if messagesPerField.existsError('password')>
          <div class="field-error">${messagesPerField.get('password')?no_esc}</div>
        </#if>
      </div>

      <#if realm.rememberMe?? && realm.rememberMe>
        <div class="remember-row">
          <input type="checkbox" id="rememberMe" name="rememberMe"
            <#if login.rememberMe?? && login.rememberMe>checked</#if> />
          <label for="rememberMe">Remember me</label>
        </div>
      </#if>

      <button type="submit" name="login" class="btn-primary">Sign In</button>
    </form>

    <div class="links">
      <#if realm.resetPasswordAllowed?? && realm.resetPasswordAllowed>
        <a href="${url.loginResetCredentialsUrl}">Forgot your password?</a>
      </#if>
    </div>

    <#if realm.registrationAllowed?? && realm.registrationAllowed && !(registrationDisabled??)>
      <div class="register-link">
        Don't have an account? <a href="${url.registrationUrl}">Create one free</a>
      </div>
    </#if>

  </div>
</body>
</html>
