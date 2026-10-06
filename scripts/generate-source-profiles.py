#!/usr/bin/env python3
"""Maintain the synthetic source catalog; preserve existing vendor plugins and scenarios.
Run from the repository root with backend/.venv/bin/python.
"""

import json
from pathlib import Path
import yaml

P = Path("products")
# Source, display name, vendor, product, schema version, formats, event families, field reference.
SOURCES = [
    (
        "windows-dc",
        "Windows Server / AD Domain Controller",
        "Microsoft",
        "Windows Security",
        "Windows Server 2022 event schema",
        ["xml", "json"],
        "logon-success logon-failure kerberos-ticket ntlm-auth account-lockout account-created group-member-added",
        "https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/advanced-security-audit-policy-settings",
    ),
    (
        "windows-sysmon",
        "Windows Sysmon",
        "Microsoft",
        "Sysmon",
        "Sysmon 15 event schema",
        ["xml", "json"],
        "process-create network-connect file-create dns-query",
        "https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon",
    ),
    (
        "linux",
        "Linux authentication and system",
        "Linux",
        "OpenSSH / sudo",
        "OpenSSH 9 / sudo 1.9",
        ["native"],
        "ssh-success ssh-failure sudo authentication kernel system",
        "https://man.openbsd.org/sshd.8",
    ),
    (
        "fortinet",
        "Fortinet FortiGate",
        "Fortinet",
        "FortiGate",
        "FortiOS 7.4",
        ["native", "cef"],
        "nat vpn authentication ips malware",
        "https://docs.fortinet.com/document/fortigate/7.4.0/fortios-log-message-reference",
    ),
    (
        "palo-alto",
        "Palo Alto PAN-OS",
        "Palo Alto Networks",
        "PAN-OS",
        "PAN-OS 11.1",
        ["csv", "cef"],
        "traffic threat url-filtering vpn configuration",
        "https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-admin/monitoring/use-syslog-for-monitoring/syslog-field-descriptions",
    ),
    (
        "check-point",
        "Check Point Log Exporter",
        "Check Point",
        "VPN-1 & FireWall-1",
        "Log Exporter R81 CEF",
        ["cef"],
        "firewall threat-prevention vpn administration",
        "https://sc1.checkpoint.com/documents/R81/WebAdminGuides/EN/CP_R81_LoggingAndMonitoring_AdminGuide/Topics-LMG/Log-Exporter-CEF-Field-Mappings.htm",
    ),
    (
        "cisco-asa",
        "Cisco ASA",
        "Cisco",
        "ASA",
        "ASA 9.20",
        ["native"],
        "connection deny nat vpn authentication",
        "https://www.cisco.com/c/en/us/td/docs/security/asa/syslog/b_syslog.html",
    ),
    (
        "cisco-ftd",
        "Cisco FTD",
        "Cisco",
        "FTD",
        "Secure Firewall 7.4",
        ["native"],
        "connection intrusion malware vpn",
        "https://www.cisco.com/c/en/us/td/docs/security/firepower/Syslogs/fptd_syslog_guide/security-event-syslog-messages.html",
    ),
    (
        "cisco-ios",
        "Cisco IOS / IOS XE",
        "Cisco",
        "IOS XE",
        "IOS XE 17",
        ["native"],
        "interface-change acl-deny login configuration",
        "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/esm/configuration/xe-17/esm-xe-17-book.html",
    ),
    (
        "juniper-srx",
        "Juniper SRX",
        "Juniper",
        "SRX",
        "Junos 23 structured syslog",
        ["native"],
        "session-create session-close deny vpn system",
        "https://www.juniper.net/documentation/us/en/software/junos/security-services/topics/topic-map/security-system-logging.html",
    ),
    (
        "sophos-firewall",
        "Sophos Firewall",
        "Sophos",
        "XG Firewall",
        "SFOS 19.5",
        ["native"],
        "firewall ips web-filter vpn authentication",
        "https://docs.sophos.com/nsg/sophos-firewall/19.5/PDF/SF-syslog-guide-19.5.pdf",
    ),
    (
        "sonicwall",
        "SonicWall",
        "SonicWall",
        "SonicOS",
        "SonicOS 7",
        ["native", "cef"],
        "traffic threat vpn authentication",
        "https://www.sonicwall.com/support/technical-documentation/docs/sonicos-7-0-0-0-device_log/Content/Logs_Syslog/settings-syslog.htm",
    ),
    (
        "watchguard",
        "WatchGuard Firebox",
        "WatchGuard",
        "Firebox",
        "Fireware 12",
        ["native"],
        "allow deny proxy vpn authentication",
        "https://www.watchguard.com/help/docs/help-center/en-US/Content/en-US/Fireware/logging/read_log-msg.html",
    ),
    (
        "f5-bigip",
        "F5 BIG-IP / Advanced WAF",
        "F5",
        "ASM",
        "BIG-IP 17 CEF",
        ["cef", "native"],
        "waf-violation blocked-request administration",
        "https://techdocs.f5.com/en-us/bigip-17-1-0/big-ip-asm-implementations/logging-application-security-events.html",
    ),
    (
        "netscaler",
        "Citrix NetScaler ADC / WAF",
        "Citrix",
        "NetScaler",
        "NetScaler 14.1",
        ["native", "cef"],
        "access authentication waf administration",
        "https://docs.netscaler.com/en-us/citrix-adc/current-release/application-firewall/logs.html",
    ),
    (
        "zscaler",
        "Zscaler ZIA NSS",
        "Zscaler",
        "NSS",
        "NSS feed schema",
        ["cef", "csv"],
        "web firewall dns administrator-audit",
        "https://help.zscaler.com/zia/nss-feed-output-format",
    ),
    (
        "cisco-umbrella",
        "Cisco Umbrella",
        "Cisco",
        "Umbrella",
        "Umbrella S3 log schema",
        ["csv", "json"],
        "dns proxy firewall",
        "https://docs.umbrella.com/deployment-umbrella/docs/log-formats-and-versioning",
    ),
    (
        "infoblox",
        "Infoblox NIOS / BloxOne",
        "Infoblox",
        "NIOS",
        "NIOS 9",
        ["native", "cef"],
        "dns-query dhcp-lease dns-threat",
        "https://docs.infoblox.com/space/nios90/220318668/Using+Syslog",
    ),
    (
        "vmware-esxi",
        "VMware ESXi",
        "VMware",
        "ESXi",
        "ESXi 8",
        ["native"],
        "authentication host-management vm-operation",
        "https://knowledge.broadcom.com/external/article?legacyId=2032076",
    ),
    (
        "aruba-clearpass",
        "Aruba ClearPass",
        "Aruba Networks",
        "ClearPass",
        "ClearPass 6.11",
        ["native", "cef"],
        "radius-auth tacacs-auth policy-decision",
        "https://arubanetworking.hpe.com/techdocs/ClearPass/6.11/PolicyManager/Content/CPPM_UserGuide/Admin/SyslogExportFilters_main.htm",
    ),
    (
        "crowdstrike",
        "CrowdStrike Falcon",
        "CrowdStrike",
        "FalconHost",
        "SIEM connector 2",
        ["cef", "json"],
        "detection prevention containment",
        "https://www.crowdstrike.com/wp-content/brochures/falcon-connector/falcon-SIEM-connector-datasheet.pdf",
    ),
    (
        "sentinelone",
        "SentinelOne",
        "SentinelOne",
        "Singularity",
        "Management API v2.1",
        ["json"],
        "threat alert agent-activity",
        "https://learn.microsoft.com/en-us/azure/sentinel/data-connectors/sentinelone",
    ),
    (
        "sophos-central",
        "Sophos Central",
        "Sophos",
        "Central",
        "SIEM API v1",
        ["json"],
        "malware behavioral pua ips",
        "https://developer.sophos.com/siem-api-schemas/",
    ),
    (
        "trend-micro",
        "Trend Micro Deep Security",
        "Trend Micro",
        "Deep Security Agent",
        "Deep Security 20 CEF",
        ["cef"],
        "malware ips integrity-monitoring",
        "https://help.deepsecurity.trendmicro.com/20_0/on-premise/Events-Alerts/syslog-parsing.html",
    ),
    (
        "okta",
        "Okta",
        "Okta",
        "System Log",
        "System Log API v1",
        ["json"],
        "sign-in denied-authentication user-change group-change application-change",
        "https://developer.okta.com/docs/reference/api/system-log/",
    ),
    (
        "entra-id",
        "Microsoft Entra ID",
        "Microsoft",
        "Entra ID",
        "SigninLogs / AuditLogs schema",
        ["json"],
        "sign-in directory-audit provisioning",
        "https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/signinlogs",
    ),
    (
        "microsoft-365",
        "Microsoft 365",
        "Microsoft",
        "Office 365",
        "Management Activity API common schema",
        ["json"],
        "exchange-audit sharepoint-audit teams-audit",
        "https://learn.microsoft.com/en-us/office/office-365-management-api/office-365-management-activity-api-schema",
    ),
    (
        "defender-xdr",
        "Microsoft Defender XDR",
        "Microsoft",
        "Defender XDR",
        "Advanced Hunting schema",
        ["json"],
        "alert process-event network-event identity-event",
        "https://learn.microsoft.com/en-us/defender-xdr/advanced-hunting-schema-tables",
    ),
    (
        "azure-activity",
        "Azure Activity",
        "Microsoft",
        "Azure",
        "Activity Log 2015-04-01 schema",
        ["json"],
        "resource-operation role-change policy-event",
        "https://learn.microsoft.com/en-us/azure/azure-monitor/platform/activity-log-schema",
    ),
    (
        "aws-cloudtrail",
        "AWS CloudTrail",
        "Amazon",
        "CloudTrail",
        "CloudTrail eventVersion 1.09",
        ["json"],
        "console-sign-in iam-api resource-api",
        "https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html",
    ),
]

V = lambda name: "{{ " + name + " }}"
TIME = "{{ generated_at_iso }}"
fields = {
    "hostname": "sim-device-01",
    "device_ip": "192.0.2.10",
    "src": "198.51.100.20",
    "dst": "203.0.113.10",
    "user": "labuser",
    "spt": 49152,
    "dpt": 443,
}
config_schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        k: {"type": "integer" if isinstance(v, int) else "string", "default": v}
        for k, v in fields.items()
    },
}
DC_IDS = {
    "logon-success": 4624,
    "logon-failure": 4625,
    "kerberos-ticket": 4769,
    "ntlm-auth": 4776,
    "account-lockout": 4740,
    "account-created": 4720,
    "group-member-added": 4728,
}
DC_DATA = {
    "logon-success": {
        "TargetUserName": V("user"),
        "TargetDomainName": "LAB",
        "TargetUserSid": "S-1-5-21-1000-1000-1000-1101",
        "TargetLogonId": "0x12345",
        "LogonType": "3",
        "IpAddress": V("src"),
        "IpPort": V("spt"),
        "AuthenticationPackageName": "Kerberos",
        "WorkstationName": V("hostname"),
    },
    "logon-failure": {
        "TargetUserName": V("user"),
        "TargetDomainName": "LAB",
        "LogonType": "3",
        "IpAddress": V("src"),
        "IpPort": V("spt"),
        "Status": "0xC000006D",
        "SubStatus": "0xC000006A",
        "FailureReason": "%%2313",
        "AuthenticationPackageName": "NTLM",
    },
    "kerberos-ticket": {
        "TargetUserName": V("user"),
        "TargetDomainName": "LAB.LOCAL",
        "ServiceName": "cifs/server01",
        "ServiceSid": "S-1-5-21-1000-1000-1000-1102",
        "TicketOptions": "0x40810000",
        "TicketEncryptionType": "0x12",
        "IpAddress": V("src"),
        "IpPort": V("spt"),
        "Status": "0x0",
        "LogonGuid": "{{ correlation_id }}",
    },
    "ntlm-auth": {
        "PackageName": "MICROSOFT_AUTHENTICATION_PACKAGE_V1_0",
        "TargetUserName": V("user"),
        "Workstation": V("hostname"),
        "Status": "0x0",
    },
    "account-lockout": {
        "TargetUserName": V("user"),
        "TargetDomainName": "LAB",
        "TargetSid": "S-1-5-21-1000-1000-1000-1101",
        "SubjectUserName": "DC01$",
        "SubjectDomainName": "LAB",
        "SubjectLogonId": "0x3e7",
        "CallerComputerName": V("hostname"),
    },
    "account-created": {
        "TargetUserName": V("user"),
        "TargetDomainName": "LAB",
        "TargetSid": "S-1-5-21-1000-1000-1000-1101",
        "SubjectUserName": "administrator",
        "SubjectDomainName": "LAB",
        "SamAccountName": V("user"),
        "UserPrincipalName": V("user") + "@lab.local",
        "NewUacValue": "0x10",
    },
    "group-member-added": {
        "TargetUserName": "Domain Admins",
        "TargetDomainName": "LAB",
        "TargetSid": "S-1-5-21-1000-1000-1000-512",
        "MemberName": "CN=" + V("user") + ",OU=Lab,DC=lab,DC=local",
        "MemberSid": "S-1-5-21-1000-1000-1000-1101",
        "SubjectUserName": "administrator",
        "SubjectDomainName": "LAB",
    },
}
SYSMON_DATA = {
    "process-create": {
        "RuleName": "-",
        "UtcTime": TIME,
        "ProcessGuid": "{{ correlation_id }}",
        "ProcessId": 1234,
        "Image": "C:\\Windows\\System32\\cmd.exe",
        "CommandLine": "cmd.exe /c whoami",
        "User": V("user"),
        "ParentProcessId": 1000,
        "ParentImage": "C:\\Windows\\explorer.exe",
        "Hashes": "SHA256=" + "a" * 64,
    },
    "network-connect": {
        "RuleName": "-",
        "UtcTime": TIME,
        "ProcessGuid": "{{ correlation_id }}",
        "ProcessId": 1234,
        "Image": "C:\\Windows\\System32\\curl.exe",
        "User": V("user"),
        "Protocol": "tcp",
        "Initiated": "true",
        "SourceIp": V("src"),
        "SourcePort": V("spt"),
        "DestinationIp": V("dst"),
        "DestinationPort": V("dpt"),
    },
    "file-create": {
        "RuleName": "-",
        "UtcTime": TIME,
        "ProcessGuid": "{{ correlation_id }}",
        "ProcessId": 1234,
        "Image": "C:\\Windows\\System32\\cmd.exe",
        "TargetFilename": "C:\\Lab\\sample.txt",
        "CreationUtcTime": TIME,
        "User": V("user"),
    },
    "dns-query": {
        "RuleName": "-",
        "UtcTime": TIME,
        "ProcessGuid": "{{ correlation_id }}",
        "ProcessId": 1234,
        "QueryName": "example.test",
        "QueryStatus": "0",
        "QueryResults": V("dst"),
        "Image": "C:\\Windows\\System32\\nslookup.exe",
        "User": V("user"),
    },
}


def cloud_record(pid, family):
    if pid == "okta":
        event = {
            "sign-in": "user.session.start",
            "denied-authentication": "user.authentication.auth_via_mfa",
            "user-change": "user.lifecycle.create",
            "group-change": "group.user_membership.add",
            "application-change": "application.lifecycle.update",
        }[family]
        return {
            "uuid": "{{ correlation_id }}",
            "published": TIME,
            "eventType": event,
            "version": "0",
            "severity": "INFO",
            "displayMessage": family,
            "actor": {
                "id": "00uLab",
                "type": "User",
                "alternateId": V("user") + "@example.test",
                "displayName": V("user"),
            },
            "client": {
                "ipAddress": V("src"),
                "userAgent": {"rawUserAgent": "Lab Simulator"},
            },
            "outcome": {
                "result": "FAILURE" if family == "denied-authentication" else "SUCCESS"
            },
            "target": [
                {
                    "id": "0oaLab",
                    "type": "AppInstance",
                    "displayName": "Lab Application",
                }
            ],
        }
    if pid == "sophos-central":
        return {
            "id": "{{ correlation_id }}",
            "created_at": TIME,
            "when": TIME,
            "type": {
                "malware": "Event::Endpoint::Threat::Detected",
                "behavioral": "Event::Endpoint::Threat::Detected",
                "pua": "Event::Endpoint::Threat::Detected",
                "ips": "Event::Endpoint::Network::Blocked",
            }[family],
            "name": family,
            "severity": "high",
            "source": V("src"),
            "location": V("hostname"),
            "endpoint_id": "11111111-2222-4333-8444-555555555555",
            "endpoint_type": "computer",
            "group": "Lab",
            "user_id": V("user"),
        }
    if pid == "cisco-umbrella":
        return {
            "Timestamp": TIME,
            "Identity": V("user"),
            "InternalIp": V("src"),
            "ExternalIp": V("device_ip"),
            "Action": "Blocked",
            "QueryType": "A",
            "ResponseCode": "NOERROR",
            "Domain": "example.test",
            "Categories": ["Malware"],
            "LogType": family,
        }
    if pid == "crowdstrike":
        return {
            "metadata": {
                "customerIDString": "a" * 32,
                "offset": 1,
                "eventType": {
                    "detection": "DetectionSummaryEvent",
                    "prevention": "DetectionSummaryEvent",
                    "containment": "UserActivityAuditEvent",
                }[family],
                "eventCreationTime": "{{ random_int(1700000000, 1799999999) }}",
                "version": "1.0",
            },
            "event": {
                "DetectId": "{{ correlation_id }}",
                "ComputerName": V("hostname"),
                "UserName": V("user"),
                "LocalIP": V("device_ip"),
                "FileName": "eicar.com",
                "Severity": 4,
                "SeverityName": "High",
                "Tactic": "Execution",
                "Technique": "User Execution",
                "PatternDispositionDescription": family,
            },
        }
    if pid == "sentinelone":
        return {
            "id": "{{ correlation_id }}",
            "createdAt": TIME,
            "activityType": 1,
            "primaryDescription": family,
            "agent": {
                "computerName": V("hostname"),
                "networkInterfaces": [{"inet": [V("device_ip")]}],
            },
            "threatInfo": {
                "threatName": "EICAR test file",
                "classification": "Malware",
                "confidenceLevel": "malicious",
                "mitigationStatus": "mitigated"
                if family != "alert"
                else "not_mitigated",
            },
            "activityUuid": "{{ correlation_id }}",
        }
    if pid == "entra-id":
        if family == "sign-in":
            return {
                "TimeGenerated": TIME,
                "Id": "{{ correlation_id }}",
                "UserPrincipalName": V("user") + "@example.test",
                "UserId": "11111111-2222-4333-8444-555555555555",
                "AppDisplayName": "Lab application",
                "AppId": "11111111-2222-4333-8444-666666666666",
                "IPAddress": V("src"),
                "ResultType": "0",
                "ResultDescription": "Success",
                "ConditionalAccessStatus": "success",
                "ClientAppUsed": "Browser",
                "IsInteractive": True,
            }
        if family == "provisioning":
            return {
                "TimeGenerated": TIME,
                "Id": "{{ correlation_id }}",
                "Action": "Create",
                "SourceSystem": {"displayName": "Entra ID"},
                "TargetSystem": {"displayName": "Lab SCIM application"},
                "StatusInfo": {"status": "success"},
                "SourceIdentity": {"displayName": V("user")},
            }
        return {
            "TimeGenerated": TIME,
            "Id": "{{ correlation_id }}",
            "OperationName": "Add user",
            "Category": "UserManagement",
            "Result": "success",
            "InitiatedBy": {
                "user": {
                    "userPrincipalName": "admin@example.test",
                    "ipAddress": V("src"),
                }
            },
            "TargetResources": [{"displayName": V("user"), "type": "User"}],
        }
    if pid == "microsoft-365":
        return {
            "CreationTime": TIME,
            "Id": "{{ correlation_id }}",
            "Operation": {
                "exchange-audit": "MailItemsAccessed",
                "sharepoint-audit": "FileAccessed",
                "teams-audit": "TeamsSessionStarted",
            }[family],
            "RecordType": {
                "exchange-audit": 50,
                "sharepoint-audit": 6,
                "teams-audit": 25,
            }[family],
            "Workload": {
                "exchange-audit": "Exchange",
                "sharepoint-audit": "SharePoint",
                "teams-audit": "MicrosoftTeams",
            }[family],
            "UserId": V("user") + "@example.test",
            "UserType": 0,
            "OrganizationId": "11111111-2222-4333-8444-555555555555",
            "ClientIP": V("src"),
            "ResultStatus": "Succeeded",
            "ObjectId": "https://example.test/lab/sample.txt",
            "Version": 1,
        }
    if pid == "defender-xdr":
        common = {
            "Timestamp": TIME,
            "DeviceId": "a" * 40,
            "DeviceName": V("hostname"),
            "ReportId": 1,
        }
        if family == "alert":
            return {
                "Timestamp": TIME,
                "AlertId": "{{ correlation_id }}",
                "Title": "Simulated malware detection",
                "Category": "Malware",
                "Severity": "High",
                "ServiceSource": "Microsoft Defender for Endpoint",
                "DetectionSource": "Antivirus",
            }
        if family == "process-event":
            return {
                **common,
                "ActionType": "ProcessCreated",
                "FileName": "cmd.exe",
                "FolderPath": "C:\\Windows\\System32",
                "ProcessCommandLine": "cmd.exe /c whoami",
                "AccountName": V("user"),
                "ProcessId": 1234,
            }
        if family == "network-event":
            return {
                **common,
                "ActionType": "ConnectionSuccess",
                "RemoteIP": V("dst"),
                "RemotePort": 443,
                "LocalIP": V("src"),
                "LocalPort": 49152,
                "Protocol": "Tcp",
                "InitiatingProcessFileName": "curl.exe",
            }
        return {
            "Timestamp": TIME,
            "ReportId": 1,
            "ActionType": "LogonSuccess",
            "AccountName": V("user"),
            "AccountDomain": "LAB",
            "IPAddress": V("src"),
            "Application": "Active Directory",
            "Protocol": "Kerberos",
        }
    if pid == "azure-activity":
        op = {
            "resource-operation": "Microsoft.Compute/virtualMachines/write",
            "role-change": "Microsoft.Authorization/roleAssignments/write",
            "policy-event": "Microsoft.Authorization/policies/audit/action",
        }[family]
        return {
            "time": TIME,
            "resourceId": "/subscriptions/11111111-2222-4333-8444-555555555555/resourceGroups/lab/providers/Microsoft.Compute/virtualMachines/vm01",
            "operationName": op,
            "category": "Administrative" if family != "policy-event" else "Policy",
            "resultType": "Success",
            "caller": V("user") + "@example.test",
            "correlationId": "{{ correlation_id }}",
            "level": "Informational",
            "properties": {"statusCode": "OK"},
            "claims": {"ipaddr": V("src")},
        }
    if pid == "aws-cloudtrail":
        return {
            "eventVersion": "1.09",
            "userIdentity": {
                "type": "IAMUser",
                "principalId": "AIDALAB",
                "arn": "arn:aws:iam::123456789012:user/" + V("user"),
                "accountId": "123456789012",
                "userName": V("user"),
            },
            "eventTime": TIME,
            "eventSource": {
                "console-sign-in": "signin.amazonaws.com",
                "iam-api": "iam.amazonaws.com",
                "resource-api": "ec2.amazonaws.com",
            }[family],
            "eventName": {
                "console-sign-in": "ConsoleLogin",
                "iam-api": "CreateUser",
                "resource-api": "RunInstances",
            }[family],
            "awsRegion": "us-east-1",
            "sourceIPAddress": V("src"),
            "userAgent": "Lab Simulator",
            "requestParameters": None,
            "responseElements": {"ConsoleLogin": "Success"}
            if family == "console-sign-in"
            else {},
            "eventID": "{{ correlation_id }}",
            "eventType": "AwsConsoleSignIn"
            if family == "console-sign-in"
            else "AwsApiCall",
            "managementEvent": True,
            "recipientAccountId": "123456789012",
            "eventCategory": "Management",
        }
    return None


NATIVE = {
    "linux": {
        "ssh-success": "sshd[1234]: Accepted password for {{ user }} from {{ src }} port {{ spt }} ssh2",
        "ssh-failure": "sshd[1234]: Failed password for {{ user }} from {{ src }} port {{ spt }} ssh2",
        "sudo": "sudo: {{ user }} : TTY=pts/0 ; PWD=/home/{{ user }} ; USER=root ; COMMAND=/usr/bin/id",
        "authentication": "sshd[1234]: pam_unix(sshd:session): session opened for user {{ user }} by (uid=0)",
        "kernel": "kernel: IN=eth0 OUT= MAC=00:11:22:33:44:55 SRC={{ src }} DST={{ dst }} PROTO=TCP SPT={{ spt }} DPT={{ dpt }}",
        "system": "systemd[1]: Started Lab Service.",
    },
    "fortinet": {
        "nat": 'date={{ generated_at_iso[:10] }} time=12:00:00 devname="{{ hostname }}" devid="FGTSIM00000001" logid="0000000013" type="traffic" subtype="forward" level="notice" srcip={{ src }} dstip={{ dst }} srcport={{ spt }} dstport={{ dpt }} action="accept" trandisp="snat" transip={{ device_ip }} transport=60000',
        "vpn": 'devname="{{ hostname }}" logid="0101037127" type="event" subtype="vpn" action="tunnel-up" remip={{ src }} locip={{ device_ip }} vpntunnel="Lab-IPSec" status="success"',
        "authentication": 'devname="{{ hostname }}" logid="0102043008" type="event" subtype="user" action="authentication" user="{{ user }}" srcip={{ src }} status="success"',
        "ips": 'devname="{{ hostname }}" logid="0419016384" type="utm" subtype="ips" eventtype="signature" srcip={{ src }} dstip={{ dst }} attack="Lab signature" action="dropped"',
        "malware": 'devname="{{ hostname }}" logid="0211008192" type="utm" subtype="virus" srcip={{ src }} dstip={{ dst }} virus="EICAR_TEST_FILE" filename="eicar.com" action="blocked"',
    },
    "cisco-asa": {
        "connection": "%ASA-6-302013: Built outbound TCP connection 1234 for outside:{{ dst }}/{{ dpt }} ({{ dst }}/{{ dpt }}) to inside:{{ src }}/{{ spt }} ({{ src }}/{{ spt }})",
        "deny": '%ASA-4-106023: Deny tcp src outside:{{ src }}/{{ spt }} dst inside:{{ dst }}/{{ dpt }} by access-group "LAB" [0x0, 0x0]',
        "nat": "%ASA-6-305011: Built dynamic TCP translation from inside:{{ src }}/{{ spt }} to outside:{{ device_ip }}/60000",
        "vpn": "%ASA-6-713119: Group = LabVPN, IP = {{ src }}, PHASE 1 COMPLETED",
        "authentication": "%ASA-6-113004: AAA user authentication Successful : server = {{ dst }} : user = {{ user }}",
    },
    "cisco-ftd": {
        "connection": "%FTD-6-302013: Built outbound TCP connection 1234 for outside:{{ dst }}/{{ dpt }} to inside:{{ src }}/{{ spt }}",
        "intrusion": "%FTD-4-430001: DeviceUUID: 11111111-2222-4333-8444-555555555555, InstanceID: 1, FirstPacketSecond: {{ generated_at_iso }}, ConnectionID: 1234, SrcIP: {{ src }}, DstIP: {{ dst }}, SrcPort: {{ spt }}, DstPort: {{ dpt }}, Protocol: tcp, GID: 1, SID: 1000001, Message: Lab intrusion, Classification: attempted-admin, Priority: 1",
        "malware": "%FTD-4-430005: DeviceUUID: 11111111-2222-4333-8444-555555555555, InstanceID: 1, SrcIP: {{ src }}, DstIP: {{ dst }}, FileName: eicar.com, FileSHA256: "
        + ("a" * 64)
        + ", FileDisposition: Malware",
        "vpn": "%FTD-6-713119: Group = LabVPN, IP = {{ src }}, PHASE 1 COMPLETED",
    },
    "cisco-ios": {
        "interface-change": "%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down",
        "acl-deny": "%SEC-6-IPACCESSLOGP: list LAB denied tcp {{ src }}({{ spt }}) -> {{ dst }}({{ dpt }}), 1 packet",
        "login": "%SEC_LOGIN-5-LOGIN_SUCCESS: Login Success [user: {{ user }}] [Source: {{ src }}] [localport: 22]",
        "configuration": "%SYS-5-CONFIG_I: Configured from console by {{ user }} on vty0 ({{ src }})",
    },
    "juniper-srx": {
        "session-create": "RT_FLOW: RT_FLOW_SESSION_CREATE: session created {{ src }}/{{ spt }}->{{ dst }}/{{ dpt }} junos-https {{ src }}/{{ spt }}->{{ dst }}/{{ dpt }} None None 6 LAB trust untrust 1234 N/A(N/A) ge-0/0/0.0 UNKNOWN UNKNOWN UNKNOWN",
        "session-close": "RT_FLOW: RT_FLOW_SESSION_CLOSE: TCP FIN {{ src }}/{{ spt }}->{{ dst }}/{{ dpt }} junos-https {{ src }}/{{ spt }}->{{ dst }}/{{ dpt }} None None 6 LAB trust untrust 1234 10(1000) 10(1000) 5 N/A(N/A) ge-0/0/0.0 UNKNOWN UNKNOWN UNKNOWN",
        "deny": "RT_FLOW: RT_FLOW_SESSION_DENY: {{ src }}/{{ spt }}->{{ dst }}/{{ dpt }} junos-https 6 LAB trust untrust UNKNOWN UNKNOWN UNKNOWN",
        "vpn": "kmd[1234]: KMD_VPN_UP_ALARM_USER: VPN LabVPN from {{ src }} is up",
        "system": "mgd[1234]: UI_COMMIT_COMPLETED: commit complete by {{ user }}",
    },
    "sophos-firewall": {
        "*": 'device_name="{{ hostname }}" device_id="C01001LAB" log_id="010101600001" log_type="Firewall" log_component="Firewall Rule" log_subtype="Allowed" priority="Information" src_ip={{ src }} dst_ip={{ dst }} src_port={{ spt }} dst_port={{ dpt }} protocol="TCP" user_name="{{ user }}" status="Allow"'
    },
    "sonicwall": {
        "*": 'id=firewall sn=LAB000001 time="{{ generated_at_iso }}" fw={{ device_ip }} pri=6 c=1024 m=97 msg="Connection Opened" src={{ src }}:{{ spt }}:X0 dst={{ dst }}:{{ dpt }}:X1 proto=tcp/https user="{{ user }}"'
    },
    "watchguard": {
        "*": '{{ hostname }} Allow {{ src }} {{ dst }} https/tcp {{ spt }} {{ dpt }} Trusted External (LabPolicy) proc_id="firewall" rc="100" msg_id="3000-0148"'
    },
    "f5-bigip": {
        "*": 'ASM: unit_hostname="{{ hostname }}",management_ip_address="{{ device_ip }}",http_class_name="/Common/Lab",policy_name="/Common/Lab",violations="Illegal URL",support_id="123456789",request_status="blocked",ip_client="{{ src }}",method="GET",uri="/lab"'
    },
    "netscaler": {
        "*": "{{ hostname }} 0-PPE-0 : default APPFW APPFW_POLICY_ACTION 1234 0 : {{ src }} 1234-PPE0 - lab_policy http://example.test/lab BLOCK"
    },
    "infoblox": {
        "dns-query": "named[1234]: client {{ src }}#{{ spt }} (example.test): query: example.test IN A + ({{ device_ip }})",
        "dhcp-lease": "dhcpd[1234]: DHCPACK on {{ src }} to 00:11:22:33:44:55 ({{ hostname }}) via eth0",
        "dns-threat": "named[1234]: client {{ src }}#{{ spt }} (malware.test): rpz QNAME NXDOMAIN rewrite malware.test via malware.test.rpz.lab",
    },
    "vmware-esxi": {
        "authentication": "Hostd: [Originator@6876 sub=Vimsvc.ha-eventmgr] Event 123 : User {{ user }}@{{ src }} logged in as VMware-client",
        "host-management": "Hostd: [Originator@6876 sub=Vimsvc] Task Created : haTask-ha-host-vim.HostSystem.reconfigure-123",
        "vm-operation": "Hostd: [Originator@6876 sub=Vimsvc.ha-eventmgr] Event 124 : Virtual machine LabVM powered on",
    },
    "aruba-clearpass": {
        "*": "CPPM_Logs: {{ generated_at_iso }} {{ hostname }} RADIUS: Request ID=1234 User-Name={{ user }} NAS-IP-Address={{ src }} Service=Lab-RADIUS Authentication-Status=Success Enforcement-Profile=Allow-Access"
    },
}
# Override family-specific classifications rather than changing only the display label.
NATIVE["sophos-firewall"].update(
    {
        "ips": NATIVE["sophos-firewall"]["*"]
        .replace('log_type="Firewall"', 'log_type="IPS"')
        .replace('log_component="Firewall Rule"', 'log_component="Signatures"')
        .replace('log_subtype="Allowed"', 'log_subtype="Drop"'),
        "web-filter": NATIVE["sophos-firewall"]["*"]
        .replace('log_type="Firewall"', 'log_type="Content Filtering"')
        .replace('log_component="Firewall Rule"', 'log_component="HTTP"')
        + ' url="http://example.test/lab"',
        "vpn": 'device_name="{{ hostname }}" log_type="Event" log_component="SSL VPN" log_subtype="Authentication" user_name="{{ user }}" src_ip={{ src }} status="Success"',
        "authentication": 'device_name="{{ hostname }}" log_type="Event" log_component="Authentication" user_name="{{ user }}" src_ip={{ src }} status="Success"',
    }
)
NATIVE["sonicwall"].update(
    {
        "threat": NATIVE["sonicwall"]["*"]
        .replace("c=1024 m=97", "c=16 m=609")
        .replace("Connection Opened", "Gateway Anti-Virus Alert: EICAR"),
        "vpn": NATIVE["sonicwall"]["*"]
        .replace("c=1024 m=97", "c=16 m=358")
        .replace("Connection Opened", "IPSec tunnel established"),
        "authentication": NATIVE["sonicwall"]["*"]
        .replace("c=1024 m=97", "c=16 m=254")
        .replace("Connection Opened", "User login successful"),
    }
)
NATIVE["watchguard"].update(
    {
        "deny": NATIVE["watchguard"]["*"]
        .replace("Allow", "Deny")
        .replace("3000-0148", "3000-0149"),
        "proxy": NATIVE["watchguard"]["*"]
        + ' proxy_act="HTTP-Lab" op="GET" dstname="example.test"',
        "vpn": "iked[1234]: IKEv2 SA established to {{ src }} for peer LabVPN",
        "authentication": "admd[1234]: User {{ user }} from {{ src }} authenticated successfully",
    }
)
NATIVE["f5-bigip"]["administration"] = (
    "mcpd[1234]: 01070417:5: AUDIT - user {{ user }} - transaction #123 - object /Common/Lab - modify"
)
NATIVE["netscaler"].update(
    {
        "access": "{{ hostname }} 0-PPE-0 : default HTTP REQUEST 1234 0 : Client_ip {{ src }} Client_port {{ spt }} Vserver_ip {{ dst }} Vserver_port {{ dpt }} Method GET Url /lab",
        "authentication": "{{ hostname }} 0-PPE-0 : default AAA LOGIN 1234 0 : User {{ user }} - Remote_ip {{ src }} - Result Success",
        "administration": '{{ hostname }} 0-PPE-0 : default CLI CMD_EXECUTED 1234 0 : User {{ user }} - Remote_ip {{ src }} - Command "show ns version"',
    }
)
NATIVE["aruba-clearpass"].update(
    {
        "tacacs-auth": NATIVE["aruba-clearpass"]["*"]
        .replace("RADIUS", "TACACS")
        .replace("Lab-RADIUS", "Lab-TACACS"),
        "policy-decision": NATIVE["aruba-clearpass"]["*"]
        + " Role=Lab-Employee Posture-Status=HEALTHY",
    }
)

catalog = []
for pid, name, vendor, product, version, formats, families, reference in SOURCES:
    root = P / pid
    root.mkdir(exist_ok=True)
    (root / "scenarios").mkdir(exist_ok=True)
    manifest_path = root / "manifest.yaml"
    existing = (
        yaml.safe_load(manifest_path.read_text()) if manifest_path.exists() else None
    )
    manifest = existing or {
        "id": pid,
        "display_name": name,
        "version": "1.0.0",
        "supported_modes": ["push_webhook"],
        "supported_auth_methods": ["none", "basic", "bearer", "api_key_header"],
        "scenarios": [],
    }
    manifest["supported_modes"] = list(
        dict.fromkeys(manifest.get("supported_modes", []) + ["push_webhook"])
    )
    manifest["supported_auth_methods"] = list(
        dict.fromkeys(
            manifest.get("supported_auth_methods", [])
            + ["none", "basic", "bearer", "api_key_header"]
        )
    )
    manifest["supported_transports"] = list(
        dict.fromkeys(
            manifest.get("supported_transports", [])
            + ["syslog", "http_webhook", "azure_logs_ingestion"]
        )
    )
    manifest.update(
        formats=formats,
        field_references=[reference],
        schema_version=version,
        compatibility="Synthetic ingestion; native service connector not reproduced"
        if "json" in formats and pid not in ("windows-dc", "windows-sysmon")
        else "Representative synthetic wire format; live vendor parser validation required",
    )
    catalog.append(
        {
            "id": pid,
            "name": name,
            "formats": formats,
            "schema_version": version,
            "families": families.split(),
            "references": [reference],
            "compatibility": manifest["compatibility"],
        }
    )
    for index, family in enumerate(families.split()):
        sid = (
            "sim-" + family if pid in ("fortinet", "okta", "sophos-central") else family
        )
        default = (
            "xml"
            if pid.startswith("windows-")
            else "native"
            if "native" in formats
            else formats[0]
        )
        logical = {
            "vendor": vendor,
            "product": product,
            "version": version,
            "family": family,
            "name": family.replace("-", " ").title(),
            "signature": str(1000 + index),
            "severity": 5,
            "default_format": default,
            "time": TIME,
            **{k: V(k) for k in fields},
            "action": "blocked"
            if any(
                w in family
                for w in (
                    "deny",
                    "threat",
                    "malware",
                    "failure",
                    "ips",
                    "intrusion",
                    "violation",
                )
            )
            else "allowed",
        }
        if pid == "trend-micro":
            logical["signature"] = {
                "malware": "4000000",
                "ips": "1001111",
                "integrity-monitoring": "2002779",
            }[family]
            logical["cef_extensions"] = {
                "cn1": "1",
                "cn1Label": "Host ID",
                "filePath": "C:\\Lab\\eicar.com"
                if family == "malware"
                else "/etc/passwd",
                "act": "IDS:Reset"
                if family == "ips"
                else "updated"
                if family == "integrity-monitoring"
                else "quarantined",
            }
        elif pid == "crowdstrike":
            logical["signature"] = {
                "detection": "DetectionSummaryEvent",
                "prevention": "DetectionSummaryEvent",
                "containment": "UserActivityAuditEvent",
            }[family]
            logical["cef_extensions"] = {
                "fileName": "eicar.com",
                "cs1": "Execution",
                "cs1Label": "Tactic",
                "cs2": "User Execution",
                "cs2Label": "Technique",
            }
        elif pid == "f5-bigip":
            logical["signature"] = "ASM" if family != "administration" else "AUDIT"
            logical["cef_extensions"] = {
                "request": "http://example.test/lab",
                "requestMethod": "GET",
                "cs1": "/Common/Lab",
                "cs1Label": "policy_name",
                "cs2": "Illegal URL",
                "cs2Label": "violations",
                "act": "blocked" if family != "administration" else "modify",
            }
        elif pid == "check-point":
            logical["signature"] = family
            logical["cef_extensions"] = {
                "cs1": "LabPolicy",
                "cs1Label": "Rule Name",
                "deviceDirection": "0",
            }
        elif pid == "aruba-clearpass":
            logical["signature"] = family
            logical["cef_extensions"] = {
                "cs1": "Lab-RADIUS",
                "cs1Label": "Service",
                "cs2": "Allow-Access",
                "cs2Label": "Enforcement Profile",
                "outcome": "Success",
            }
        elif pid == "palo-alto":
            logical["signature"] = {
                "traffic": "TRAFFIC",
                "threat": "THREAT",
                "url-filtering": "THREAT",
                "vpn": "SYSTEM",
                "configuration": "CONFIG",
            }[family]
            logical["cef_extensions"] = {
                "cs1": "LabPolicy",
                "cs1Label": "Rule",
                "cs2": "vsys1",
                "cs2Label": "Virtual System",
                "cs3": "ssl",
                "cs3Label": "Application",
                "cn1": "1234",
                "cn1Label": "Session ID",
            }
        record = cloud_record(pid, family) or {
            "TimeGenerated": TIME,
            "Computer": V("hostname"),
            "SourceIP": V("src"),
            "DestinationIP": V("dst"),
            "UserName": V("user"),
            "EventFamily": family,
            "CorrelationId": "{{ correlation_id }}",
        }
        if pid == "windows-dc":
            logical["signature"] = str(DC_IDS[family])
            record = {
                "TimeGenerated": TIME,
                "Computer": V("hostname"),
                "EventID": DC_IDS[family],
                "EventRecordId": "{{ event_sequence + 1 }}",
                "Channel": "Security",
                "Provider": "Microsoft-Windows-Security-Auditing",
                "EventData": DC_DATA[family],
            }
        elif pid == "windows-sysmon":
            ids = {
                "process-create": 1,
                "network-connect": 3,
                "file-create": 11,
                "dns-query": 22,
            }
            logical["signature"] = str(ids[family])
            record = {
                "TimeGenerated": TIME,
                "Computer": V("hostname"),
                "EventID": ids[family],
                "EventRecordId": "{{ event_sequence + 1 }}",
                "Channel": "Microsoft-Windows-Sysmon/Operational",
                "Provider": "Microsoft-Windows-Sysmon",
                "EventData": SYSMON_DATA[family],
            }
        body = {"_source_event": logical, "record": record}
        if pid in NATIVE:
            body["native"] = NATIVE[pid].get(family, NATIVE[pid].get("*", ""))
        if pid == "palo-alto":
            kind = {
                "traffic": "TRAFFIC",
                "threat": "THREAT",
                "url-filtering": "THREAT",
                "vpn": "SYSTEM",
                "configuration": "CONFIG",
            }[family]
            sub = {
                "traffic": "end",
                "threat": "vulnerability",
                "url-filtering": "url",
                "vpn": "globalprotect",
                "configuration": "0",
            }[family]
            if kind in ("TRAFFIC", "THREAT"):
                body["csv"] = [
                    "1",
                    TIME,
                    "012345678901",
                    kind,
                    sub,
                    "1",
                    TIME,
                    V("src"),
                    V("dst"),
                    "0.0.0.0",
                    "0.0.0.0",
                    "LabPolicy",
                    V("user"),
                    "",
                    "ssl",
                    "vsys1",
                    "trust",
                    "untrust",
                    "ethernet1/1",
                    "ethernet1/2",
                    "LabLog",
                    TIME,
                    "1234",
                    "1",
                    V("spt"),
                    V("dpt"),
                    "0",
                    "0",
                    "0x19",
                    "tcp",
                    "allow" if family == "traffic" else "reset-both",
                ] + (
                    [
                        "1024",
                        "512",
                        "512",
                        "10",
                        TIME,
                        "1",
                        "any",
                        "0",
                        "1",
                        "0x0",
                        "US",
                        "US",
                        "0",
                        "5",
                        "5",
                        "tcp-fin",
                        "0",
                        "0",
                        "0",
                        "0",
                        V("hostname"),
                    ]
                    if family == "traffic"
                    else [
                        "http://example.test/lab",
                        "Lab Threat (10001)",
                        "malware",
                        "high",
                        "client-to-server",
                        "1",
                        "0x0",
                        "US",
                        "US",
                        "0",
                        "text/html",
                        "0",
                        "",
                        "0",
                        "",
                        "",
                        "0",
                        "0",
                        "0",
                        "0",
                        V("hostname"),
                    ]
                )
            elif kind == "SYSTEM":
                body["csv"] = [
                    "1",
                    TIME,
                    "012345678901",
                    kind,
                    sub,
                    "1",
                    TIME,
                    "vsys1",
                    "globalprotect-gateway-auth-succ",
                    "LabVPN",
                    "0",
                    "0",
                    "globalprotect",
                    "informational",
                    "GlobalProtect gateway authentication succeeded for " + V("user"),
                    "1",
                    "0x0",
                    "0",
                    "0",
                    "0",
                    "0",
                    V("hostname"),
                ]
            else:
                body["csv"] = [
                    "1",
                    TIME,
                    "012345678901",
                    kind,
                    "0",
                    "1",
                    TIME,
                    V("src"),
                    "vsys1",
                    "edit",
                    V("user"),
                    "Web",
                    "Succeeded",
                    "shared rules LabPolicy",
                    "1",
                    "0x0",
                    "0",
                    "0",
                    "0",
                    "0",
                    V("hostname"),
                ]
        elif pid == "zscaler":
            body["csv"] = [
                TIME,
                V("user"),
                V("src"),
                V("dst"),
                "Blocked" if family != "administrator-audit" else "Success",
                family,
                "example.test",
                "GET",
                "Malware",
                "LabPolicy",
            ]
        elif pid == "cisco-umbrella":
            if family == "dns":
                body["csv"] = [
                    TIME,
                    V("user"),
                    V("user"),
                    V("src"),
                    V("device_ip"),
                    "Blocked",
                    "A",
                    "NOERROR",
                    "example.test",
                    "Malware",
                    "DNS",
                    "Identity",
                    "",
                    "",
                ]
            elif family == "proxy":
                body["csv"] = [
                    TIME,
                    V("user"),
                    V("src"),
                    V("device_ip"),
                    V("dst"),
                    "http://example.test/lab",
                    "GET",
                    "Blocked",
                    "403",
                    "Malware",
                    "LabPolicy",
                    "Mozilla/5.0",
                    "0",
                    "0",
                ]
            else:
                body["csv"] = [
                    TIME,
                    V("user"),
                    V("src"),
                    V("spt"),
                    V("dst"),
                    V("dpt"),
                    "TCP",
                    "BLOCK",
                    "LabPolicy",
                ]
        (root / "scenarios" / f"{sid}.json").write_text(
            json.dumps({"content_type": "application/json", "body": body}, indent=2)
            + "\n"
        )
        if not any(s["id"] == sid for s in manifest["scenarios"]):
            manifest["scenarios"].append(
                {
                    "id": sid,
                    "display_name": family.replace("-", " ").title(),
                    "description": f"Synthetic {version} {family} event. See source field reference.",
                    "default_transport": "http_webhook"
                    if default in ("json", "xml")
                    else "syslog",
                    "template": f"scenarios/{sid}.json",
                    "config_schema": config_schema,
                    "supported_modes": ["push_webhook"],
                }
            )
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)
    )
    (root / "SOURCE.md").write_text(
        f'# {name}\n\nSchema: {version}. These scenarios represent documented event families with synthetic lab identities.\n\nFormats: {", ".join(formats)}. {manifest["compatibility"]}.\n\nField reference: [{version}]({reference}).\n\nCatalog coverage: {families}. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.\n'
    )
(P / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
print(f"{len(catalog)} source profiles generated")
