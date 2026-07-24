# Multilogin Kubernetes Integration - Complete Analysis & Solution

## Problem Summary

Multilogin launcher service requires:
1. **Hostname**: Must connect to `launcher.mlx.yt:45001` (hostname-locked)
2. **Protocol**: IPv6 only (listens on `:::45001`)
3. **Network**: localhost-only binding with `hostNetwork: true`
4. **Co-location**: Worker and Multilogin MUST be on the same Kubernetes node

## Issues Encountered

### 1. ❌ Initial SSL Certificate Errors
- **Problem**: Tried using service names, 127.0.0.1, localhost
- **Root Cause**: Multilogin only responds to `launcher.mlx.yt`
- **Solution**: Use `hostAliases` to map `launcher.mlx.yt` to localhost

### 2. ❌ IPv4 vs IPv6 Binding
- **Problem**: Multilogin binds to IPv6 (`:::45001`), not IPv4
- **Root Cause**: Connection refused when using IPv4 localhost
- **Solution**: Map `launcher.mlx.yt` to `::1` (IPv6 localhost)

### 3. ❌ Pod Affinity Not Working
- **Problem**: Worker pods schedule on different nodes than Multilogin
- **Root Cause**: Pod affinity rules not being enforced properly
- **Impact**: Even with `hostNetwork:true` and correct DNS, connection fails across nodes
- **Status**: **CURRENT BLOCKER**

## Required Configuration

### Worker Deployment

```yaml
spec:
  template:
    spec:
      hostNetwork: true
      dnsPolicy: ClusterFirstWithHostNet

      # Map launcher.mlx.yt to IPv6 localhost
      hostAliases:
      - ip: "::1"
        hostnames:
        - "launcher.mlx.yt"

      # CRITICAL: Force co-location with Multilogin
      affinity:
        podAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app.kubernetes.io/component
                operator: In
                values:
                - multilogin
            topologyKey: kubernetes.io/hostname

      containers:
      - name: worker
        env:
        - name: MULTILOGIN_API_URL
          value: "https://launcher.mlx.yt:45001"
        - name: SELENIUM_HOST
          value: "127.0.0.1"
        - name: DISABLE_MULTILOGIN_SSL_VERIFY
          value: "true"

        resources:
          limits:
            memory: "3Gi"  # Increased for AI + browser ops
            cpu: "2000m"
          requests:
            memory: "1Gi"
            cpu: "500m"
```

### Multilogin Deployment

```yaml
spec:
  template:
    spec:
      hostNetwork: true
      dnsPolicy: ClusterFirstWithHostNet

      hostAliases:
      - ip: "::1"
        hostnames:
        - "launcher.mlx.yt"
```

## Current Status

### ✅ Working
- DNS resolution: `launcher.mlx.yt` → `::1`
- Multilogin launcher running on port 45001 (IPv6)
- hostNetwork enabled on both deployments
- SSL handling configured properly
- Memory increased to 3Gi

### ❌ Not Working
- **Pod Affinity**: Workers still schedule on different nodes
- **Connection**: Fails because pods are on different hosts
- **Root Cause**: Pod affinity rule not enforced

## Next Steps

1. **Debug Pod Affinity**:
   - Check if there are node taints preventing co-location
   - Verify Multilogin pod has correct labels
   - Consider using nodeSelector instead of podAffinity

2. **Alternative Solution**: Use NodeSelector
   ```yaml
   # Get Multilogin node
   MULTILOGIN_NODE=$(kubectl get pod -l app.kubernetes.io/component=multilogin -n default -o jsonpath='{.items[0].spec.nodeName}')

   # Add nodeSelector to worker
   kubectl patch deployment sma-platform-social-media-automation-worker -n default --type='json' -p='[{
     "op": "add",
     "path": "/spec/template/spec/nodeSelector",
     "value": {"kubernetes.io/hostname": "'$MULTILOGIN_NODE'"}
   }]'
   ```

3. **Verify Network Access**:
   - Once co-located, test: `nc -zv ::1 45001`
   - Should return: `::1 ([::1]:45001) open`

## Testing Commands

```bash
# Check co-location
WORKER_NODE=$(kubectl get pod -l app.kubernetes.io/component=worker -n default -o jsonpath='{.items[0].spec.nodeName}')
MULTILOGIN_NODE=$(kubectl get pod -l app.kubernetes.io/component=multilogin -n default -o jsonpath='{.items[0].spec.nodeName}')
echo "Worker: $WORKER_NODE"
echo "Multilogin: $MULTILOGIN_NODE"
[ "$WORKER_NODE" = "$MULTILOGIN_NODE" ] && echo "✅ CO-LOCATED" || echo "❌ NOT CO-LOCATED"

# Test connection from worker
kubectl exec <worker-pod> -- python3 -c "
import socket
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.settimeout(2)
result = sock.connect_ex(('::1', 45001))
sock.close()
print(f'Result: {result} (0=success, 111=refused)')
"

# Test from node directly
kubectl debug node/<multilogin-node> -it --image=busybox -- nc -zv ::1 45001
```

## Timeline of Changes

1. Started with service name - SSL cert mismatch
2. Changed to 127.0.0.1 - SSL cert IP mismatch
3. Changed to localhost - SSL cert hostname mismatch
4. Changed to launcher.mlx.yt - Connection refused (IPv4)
5. Changed hostAliases to ::1 - Still connection refused
6. **Discovery**: Pods not co-located despite pod affinity
7. **Current**: Need to fix pod affinity or use nodeSelector

## Resolution

**The core issue is pod scheduling, not network configuration.**

Once pods are properly co-located on the same node with `hostNetwork:true`:
- `launcher.mlx.yt` will resolve to `::1` ✅
- Connection to `::1:45001` will succeed ✅
- SSL will be handled by `create_ssl_session()` ✅
- Campaign will execute successfully ✅
