<!DOCTYPE html>
<html lang="${locale!'en'}">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Create Account — ${realm.displayName!'Fitness Platform'}</title>
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
      max-width: 460px;
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
    .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.875rem; }
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
      margin-top: 0.5rem;
    }
    .btn-primary:hover { background: #6d28d9; }
    .login-link { text-align: center; font-size: 0.8125rem; color: #6b7280; }
    .login-link a { color: #7C3AED; font-weight: 600; text-decoration: none; }
    .login-link a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">

    <div class="brand">
      <span class="brand-fitness">Fitness</span>
      <span class="brand-platform">Platform</span>
    </div>
    <p class="card-title">Create your account</p>
    <p class="card-subtitle">Start training smarter — it's free</p>

    <#if message?has_content>
      <div class="alert alert-${message.type}">${message.summary?no_esc}</div>
    </#if>

    <form action="${url.registrationAction}" method="post">

      <div class="row-2">
        <div class="form-group">
          <label for="firstName">First name</label>
          <input type="text" id="firstName" name="firstName"
            value="${(register.formData['firstName'])!''}"
            autofocus autocomplete="given-name"
            class="<#if messagesPerField.existsError('firstName')>input-invalid</#if>" />
          <#if messagesPerField.existsError('firstName')>
            <div class="field-error">${messagesPerField.get('firstName')?no_esc}</div>
          </#if>
        </div>

        <div class="form-group">
          <label for="lastName">Last name</label>
          <input type="text" id="lastName" name="lastName"
            value="${(register.formData['lastName'])!''}"
            autocomplete="family-name"
            class="<#if messagesPerField.existsError('lastName')>input-invalid</#if>" />
          <#if messagesPerField.existsError('lastName')>
            <div class="field-error">${messagesPerField.get('lastName')?no_esc}</div>
          </#if>
        </div>
      </div>

      <div class="form-group">
        <label for="email">Email</label>
        <input type="email" id="email" name="email"
          value="${(register.formData['email'])!''}"
          autocomplete="email"
          class="<#if messagesPerField.existsError('email')>input-invalid</#if>" />
        <#if messagesPerField.existsError('email')>
          <div class="field-error">${messagesPerField.get('email')?no_esc}</div>
        </#if>
      </div>

      <#if !(realm.registrationEmailAsUsername?? && realm.registrationEmailAsUsername)>
        <div class="form-group">
          <label for="username">Username</label>
          <input type="text" id="username" name="username"
            value="${(register.formData['username'])!''}"
            autocomplete="username"
            class="<#if messagesPerField.existsError('username')>input-invalid</#if>" />
          <#if messagesPerField.existsError('username')>
            <div class="field-error">${messagesPerField.get('username')?no_esc}</div>
          </#if>
        </div>
      </#if>

      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password"
          autocomplete="new-password"
          class="<#if messagesPerField.existsError('password','password-confirm')>input-invalid</#if>" />
        <#if messagesPerField.existsError('password')>
          <div class="field-error">${messagesPerField.get('password')?no_esc}</div>
        </#if>
      </div>

      <div class="form-group">
        <label for="password-confirm">Confirm password</label>
        <input type="password" id="password-confirm" name="password-confirm"
          autocomplete="new-password"
          class="<#if messagesPerField.existsError('password-confirm')>input-invalid</#if>" />
        <#if messagesPerField.existsError('password-confirm')>
          <div class="field-error">${messagesPerField.get('password-confirm')?no_esc}</div>
        </#if>
      </div>

      <button type="submit" class="btn-primary">Create Account</button>
    </form>

    <div class="login-link">
      Already have an account? <a href="${url.loginUrl}">Sign in</a>
    </div>

  </div>
</body>
</html>
