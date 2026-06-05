; Han Translate - Inno Setup Installer Script
; Tạo file cài đặt .exe cho người dùng
; Yêu cầu: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
; Chạy sau khi build PyInstaller xong

#define AppName "Han Translate"
#define AppVersion "1.0.0"
#define AppPublisher "WooCSSIN"
#define AppURL "https://github.com/WooCSSIN/Speech-Translate"
#define AppExeName "HanTranslate.exe"
#define BuildDir "dist\HanTranslate"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Icon
SetupIconFile=ai_interpreter\assets\logo.ico
; Output
OutputDir=installer_output
OutputBaseFilename=HanTranslate_Setup_v{#AppVersion}
; Compression
Compression=lzma2/ultra64
SolidCompression=yes
; Windows version
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible
; Không cần admin (cài per-user)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Khởi động cùng Windows"; GroupDescription: "Tùy chọn:"; Flags: unchecked

[Files]
; Toàn bộ thư mục build
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; KHÔNG include file nhạy cảm (đã loại trong build)

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Gỡ cài đặt {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Xóa dữ liệu người dùng khi gỡ cài đặt (tùy chọn)
; Type: filesandordirs; Name: "{userappdata}\han_translate"

[Code]
// Kiểm tra .NET / Visual C++ runtime nếu cần
procedure InitializeWizard;
begin
  // Có thể thêm custom wizard pages ở đây
end;
