# android-ndk-local
The Android NDK is a toolset that lets you implement parts of your app in native code, using languages such as C and C++

# useage

## first clone code
```
git clone https://github.com/horatii/android-ndk-local.git
```
```shell
export ANDROID_NDK_HOME=/path/to/android-ndk/
cd android-ndk-local
conan create . 
```
## config your profile
```text
[requires]
some-requires

[tool_requirest]
android-ndk-local/1.0.0_rc1
```

```
conan install /path/to/your/code

```
