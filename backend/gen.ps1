
Add-Type -AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speak.SetOutputToWaveFile("tests/fixtures/english_onions.wav")
$speak.Speak("I have 50 kilograms of onions")
$speak.Dispose()
