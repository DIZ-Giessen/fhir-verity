import { useEffect, useState } from "react"

export { AnimatedLoadingText } from "./loading-text"

export const LodatingText = [
  "Loading",
  "Please wait",
  "Loading data",
  "Loading resources",
  "Database connection",
  "Loading settings",
  "Network connection",
]

export const LoadingUserMessage = [
  "Loading user data",
  "Loading user roles",
  "Loading user permissions",
  "Loading user settings",
  "Fetching user Tabe",
  "Fetching user Profile",
  "Fetching user Permissions",
  "Fetching user Roles",
  "Fetching user Settings",
  "Fetching user Data",
  "Fetching user Token",
  "Fetching user Profile",
  "Fetching user Permissions",
  "Fetching user Roles",
  "Fetching user Settings",
  "Fetching user Data",
]

export const LoadingCheckMessage = [
  "Checking",
  "Please wait",
  "Loading",
  "Loading data",
  "Database connection",
  "Network connection",
  "Dont quit the page",
  "This may take a while",
  "Checking the Server for matches",
  "Data Checking",
  "Fetching Data",
  "Data Checking",
  "Data Checking",
]
export const DeleteMessage = [
  "Deleting",
  "Please wait",
  "Deleting data",
  "Database connection",
  "Network connection",
  "Loading",
  "Deleting data",
  "Database connection",
  "Network connection",
  "Loading",
  "Deleting data",
  "Database connection",
  "Network connection",
  "Loading",
  "Counting the entries to delete",
  "Deleting data",
  "Database connection",
  "Network connection",
  "Loading",
  "Deleting data",
  "Database connection",
  "Network connection",
  "Loading",
]

export const PurgeText = [
  "Purging",
  "Please wait",
  "Purging data",
  "Database connection",
  "Network connection",
  "Loading",
]

export const useLoadingText = (texts: string[]) => {
  const [loadingText, setLoadingText] = useState(texts[0])
  useEffect(() => {
    const interval = setInterval(() => {
      setLoadingText(texts[Math.floor(Math.random() * texts.length)])
    }, 3000)
    return () => clearInterval(interval)
  }, [texts])
  return loadingText
}
