module Main (main) where

main :: IO ()
main = print (map 42)

map :: Integer -> Integer
map = id
